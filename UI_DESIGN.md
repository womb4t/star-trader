# Controls design notes

Applied guidance:
- [Xbox Accessibility Guideline 107: Input](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/107): support keyboard and mouse paths.
- [Xbox Accessibility Guideline 112: UI navigation](https://learn.microsoft.com/en-my/gaming/accessibility/xbox-accessibility-guidelines/112): consistent navigation placement and focus matching visual order.
- [Nielsen Norman Group usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/): recognition over recall, visible state, clear labels, reduced clutter.

Implementation: common navigation bar; utilities grouped in Menu; separate contextual flight controls; six controls topics; persistent toggle labels; 32px mouse targets; keyboard focus in Menu and jobs; consistent return actions. The existing keyboard shortcuts are retained. This is an incremental cleanup, not a claim of full accessibility compliance; remapping and full screen-reader support are future work.
