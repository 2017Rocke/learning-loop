# Sources and attribution

Learning Loop's original application code, explanations, example calculations,
diagrams, and teaching assets are provided under the root MIT license. Material
quoted from another project retains its original license.

## Brush source excerpts

- Project: [ArthurBrussee/brush](https://github.com/ArthurBrussee/brush)
- Author/project maintainer: Arthur Brussee and Brush contributors
- Fixed revision used in `content/brush.json`:
  `1388f74c6fe0236f68ee4915564bf00e9d2e3747`
- License: Apache License 2.0. A copy of the upstream license is preserved in
  [`licenses/brush-LICENSE.txt`](licenses/brush-LICENSE.txt).
- Continuous source excerpts retain the original text. Chinese annotations are
  separate teaching notes written for this project; the short pseudocode is
  explicitly labeled and is not represented as upstream source.

The course's Gaussian animation and diagrams are original teaching illustrations,
not Brush reconstruction output. Linked papers, official documentation, and
videos remain on their original sites; their links do not relicense those works.

## Narration

Packaged narration is synthesized from the project's original Chinese scripts.
Brush and VoiceStudio use the installed macOS Tingting voice; the refreshed Bayes
course uses Microsoft Edge's `zh-CN-XiaoxiaoNeural` voice through the optional
`edge-tts` authoring tool. Its public lesson scripts are sent for online synthesis
during explicit authoring, and the resulting files are bundled for offline
playback. No model files or third-party recordings are included. Regeneration
requires the appropriate optional tools and, for neural narration, an available
online service. Duration and actual voice provenance are recorded in each lesson.

## Bayes course

The factory and email examples use synthetic teaching assumptions and original
cartoon-style diagrams. Characters guide attention; only labeled counts or
explicitly scaled dots represent quantities.
The source references link to Stanford and OpenStax explanations; no textbook
page scans, copied lecture recordings, or third-party video files are bundled.

## VoiceStudio source excerpts

- Project: [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio)
- Fixed revision used in `content/voicestudio.json`:
  `7703ca66da77b8d130e6d1d3b2e67d979fa5a77f`
- Continuous excerpts: `backend/services/chunked_tts.py`, lines 153–176,
  451–467 and 484–506. Chinese annotations are separate original explanations.
- Upstream repository license: GNU Affero General Public License v3.0;
  full text in [`licenses/voicestudio-AGPL-3.0.txt`](licenses/voicestudio-AGPL-3.0.txt).
- The source module additionally states: “Adapted from voicebox
  (https://github.com/jamiepine/voicebox), MIT License,
  Copyright (c) voicebox contributors.” This attribution is retained here and in
  the course; excerpts are not relicensed under Learning Loop's MIT license.
- Voicebox's complete MIT notice is preserved in
  [`licenses/voicebox-MIT.txt`](licenses/voicebox-MIT.txt), obtained from fixed
  revision `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f`, `LICENSE`.
- Both license texts are also carried as plain `license_text` data on the course's
  corresponding source references, so data-only Android course updates include
  the notices even though they do not replace an installed APK's credits page.

The four diagrams and the punctuation listening exercise are original teaching
illustrations. All ten narration clips use the installed system Tingting voice;
none is presented as a VoiceStudio model-quality demonstration. No VoiceStudio
application, model weights, or third-party voice recordings are bundled.
