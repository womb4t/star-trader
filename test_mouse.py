"""Exercise real SDL event scaling and clickable UI using a headless renderer."""
import ctypes as C
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import star_trader as st


class MouseIntegrationTests(unittest.TestCase):
    def test_scaled_mouse_events_hit_jobs_answers_and_held_controls(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,SDL_VIDEODRIVER='dummy',STAR_TRADER_NO_UPDATE_CHECK='1'), patch.object(st,'SAVE',Path(directory)/'save.json'):
            d = st.Display()
            try:
                resize = st.bind(d.sdl,'SDL_SetWindowSize',None,[C.c_void_p,C.c_int,C.c_int])
                push = st.bind(d.sdl,'SDL_PushEvent',C.c_int,[C.c_void_p])
                window_id = st.bind(d.sdl,'SDL_GetWindowID',C.c_uint32,[C.c_void_p])(d.win)
                to_window = st.bind(d.sdl,'SDL_RenderLogicalToWindow',None,[C.c_void_p,C.c_float,C.c_float,C.POINTER(C.c_int),C.POINTER(C.c_int)])

                def mouse(g,x,y,down=True):
                    wx,wy = C.c_int(),C.c_int()
                    to_window(d.r,x,y,C.byref(wx),C.byref(wy))
                    raw = bytearray(56)
                    struct.pack_into('=I',raw,0,1025 if down else 1026)
                    struct.pack_into('=I',raw,8,window_id)
                    raw[16],raw[17] = 1,int(down)
                    struct.pack_into('=ii',raw,20,wx.value,wy.value)
                    event = (C.c_uint64*7).from_buffer_copy(raw)
                    self.assertEqual(push(C.byref(event)),1)
                    delivered = list(d.events())
                    expected = 'click' if down else 'mouse_up'
                    points = [point for kind,point in delivered if kind == expected]
                    self.assertEqual(len(points),1)
                    self.assertAlmostEqual(points[0][0],x,delta=2)
                    self.assertAlmostEqual(points[0][1],y,delta=2)
                    if down: g.click(*points[0])
                    else: g.release_mouse()

                for width,height in [(1100,760),(1650,1140),(880,760),(1920,1080)]:
                    with self.subTest(size=(width,height)):
                        resize(d.win,width,height)
                        list(d.events())
                        st.SAVE.unlink(missing_ok=True)
                        g = st.Game(d)
                        g.mode = 'market'
                        g.draw()
                        mouse(g,200,30)
                        self.assertEqual(g.mode,'money')
                        g.draw()
                        mouse(g,150,550)
                        self.assertEqual(g.mode,'jobs')
                        g.draw()
                        mouse(g,500,180)
                        self.assertEqual(g.p.dock_job['kind'],0)
                        g.draw()
                        answer = g.p.dock_job['answer']
                        mouse(g,200,350+answer*55)
                        self.assertEqual(g.p.dock_job['correct'],1)
                        g.mode,g.mouse_controls = 'flight',True
                        g.action_tab = 0
                        g.draw()
                        mouse(g,80,200)
                        self.assertIn(ord('w'),g.keys)
                        mouse(g,80,200,False)
                        self.assertNotIn(ord('w'),g.keys)
                        g.mode = 'market'
                        g.draw()
                        mouse(g,515,30)
                        self.assertEqual(g.mode,'menu')
                        g.draw()
                        mouse(g,100,325)
                        self.assertEqual(g.mode,'feedback')
                        raw = bytearray(56)
                        struct.pack_into('=I',raw,0,771)
                        struct.pack_into('=I',raw,8,window_id)
                        text = 'Mouse & café'.encode('utf-8')
                        raw[12:12+len(text)] = text
                        # sdl2-compat crashes when synthetic TEXTINPUT is pushed;
                        # feed the SDL2 text record at the polling boundary instead.
                        pending = [bytes(raw)]
                        def text_poll(pointer):
                            if not pending: return 0
                            C.memmove(pointer,pending.pop(),56)
                            return 1
                        with patch.object(d,'poll',side_effect=text_poll):
                            for kind,value in d.events():
                                if kind == 'text': g.text_input(value)
                        self.assertEqual(g.feedback_text,'Mouse & café')
                        g.draw()
                        mouse(g,100,688)
                        self.assertTrue(Path(g.feedback_path).exists())
                        g.key(27)
                        g.draw()
                        mouse(g,400,30)
                        self.assertEqual(g.mode,'vms')
                        g.draw()
                        mouse(g,300,30)
                        self.assertEqual(g.mode,'map')
                        self.assertEqual(g.map_return,'market')


            finally:
                d.quit()
