"""The STA Tally: the Galactic Assay Office's daily bulletin on how the economy is doing.

Modelled on a national statistics office's bulletins (output, prices, people, public finances), each led by
its main points. Published once a galactic day from figures the shared market already keeps, so it costs
nothing to run. Under the Duskholt Charter the Council funds it but can't change it.
"""
import economy

DAY = 86400
SIGN_OFF = 'Weighed, not judged. — Galactic Assay Office'


def publish(market, now):
    """Publish the day's Tally the first time the market advances into a new galactic day; None otherwise."""
    books = market.state.get('council')
    if books is None: return None
    day = int(now//DAY)
    last = market.state.get('tally')
    if last and last['day'] == day: return None
    marks = market.state.setdefault('tally_marks', dict(turnover=0., lost=0.))
    output = books.get('turnover', 0.)-marks['turnover']
    lost = market.state.get('contraband_lost', 0.)-marks['lost']
    marks.update(turnover=books.get('turnover', 0.), lost=market.state.get('contraband_lost', 0.))
    before = last['figures']['output'] if last else None
    names = getattr(market, 'names', None) or [str(i) for i in range(len(market.stock))]
    moods = {i: economy.prosperity_label(market.state['stations'].get(str(i), {}).get('prosperity', .6)) for i in range(len(market.stock))}
    struggling = [names[i] for i in sorted(moods) if moods[i] in ('Struggling', 'Destitute')]
    figures = dict(output=round(output, 2), output_change=(output/before-1) if before else None,
                   inflation=books.get('inflation', 0.), rate=books.get('rate', .05), tax=books.get('base_tax', 0.),
                   treasury=round(books.get('treasury', 0.)), contraband_lost=round(lost, 1),
                   **{mood.lower(): sum(1 for m in moods.values() if m == mood) for mood in ('Thriving', 'Comfortable', 'Struggling', 'Destitute')})
    report = dict(day=day, published=now, figures=figures, points=main_points(figures, struggling), sign_off=SIGN_OFF)
    market.state['tally'] = report
    return report


def main_points(figures, struggling):
    change, inflation = figures['output_change'], figures['inflation']
    points = [f'Galactic output was {figures["output"]:,.0f} cr.' if change is None else
              f'Galactic output {"rose" if change >= 0 else "fell"} {abs(change)*100:.1f}% on the day.',
              f'Prices {"rose" if inflation >= 0 else "fell"} {abs(inflation)*100:.1f}%; the Council\'s rate is {figures["rate"]*100:.1f}%.',
              'Every world is comfortable or better.' if not struggling else
              f'{len(struggling)} world{"s" if len(struggling) > 1 else ""} struggling: {", ".join(struggling)}.']
    if figures['contraband_lost'] >= 1: points.append(f'Customs and pirates took {figures["contraband_lost"]:,.0f} t of contraband.')
    return points
