# Making an Explanatory Video

A codebase explainer for someone about to open their first PR. A demo sells an
outcome; an explainer builds a mental map, so the viewer finishes knowing which
directory to open for the change they have in mind. The video is an animated
diagram, not a screen recording, and it follows the same deterministic HTML
contract and MP4 export as a demo.

## Contents

- [References](#references)
- [Workflow](#workflow)
- [Scope: one layer, five boxes](#scope-one-layer-five-boxes)
- [Verify against the source](#verify-against-the-source)
- [Story: follow one request](#story-follow-one-request)
- [Layout: a fixed stage](#layout-a-fixed-stage)
- [Progressive disclosure](#progressive-disclosure)
- [Labels and captions](#labels-and-captions)
- [Pacing](#pacing)
- [Ending: where your code goes](#ending-where-your-code-goes)

## References

- [Making a Demo Video](making-a-demo-video.md): the `window.seek(t)`
  HTML contract, checking frames and exporting to MP4. An explainer uses all
  three unchanged; don't restate them here.
- [deslop](../deslop/SKILL.md): run every caption through it.
- Sound, if asked: the demo reference's "Generated sound effects" and
  "Generated music" sections. In an explainer, each box's first appearance
  is where its motif enters, so the score builds up with the diagram.

## Workflow

1. Read the repo's layout, then the base classes and the module that wires
   them together, before proposing anything.
2. Reply with the **one sentence** the video teaches and a **box table**
   (name, one line for a new dev, path). Get agreement on scope here; it is
   the cheapest place to cut.
3. Reply with a **beat sheet** (time range, what appears, what moves, caption)
   and the order boxes appear in. Flag any claim you inferred rather than read.
4. Check the flagged claims in the source, then build the HTML.

## Scope: one layer, five boxes

The common failure is a tour of every directory. A new contributor can't hold
twenty boxes, and a tree of folders teaches names, not how they relate.

- **Pick one layer.** For Lumen that is `lumen/ai`, not the declarative core
  too. A second layer is a second video.
- **Write the one sentence first.** For `lumen.ai`: a question goes to a
  Coordinator, which plans a chain of Agents; each agent uses the LLM and
  Tools to do one job and writes its result into a shared Context the next
  agent reads. Every box on screen must appear in that sentence.
- **Five or six boxes at most.** Leave out ingest, export, logging, UI chrome
  and utilities, even when they are large. The video is about the flow, not
  the file count.

## Verify against the source

An explainer is wrong in a way viewers act on: they open the path you showed.
Read the code behind every arrow.

- Read the base class each box stands for (`Agent` in `ai/agents/base.py`)
  and the schemas that define what moves between boxes (`input_schema` and
  `output_schema`, `ContextModel` in `ai/context.py`).
- Use the real key names on tokens (`source`, `sql`, `pipeline`, `view`), the
  real class names on boxes (`SQLAgent`, `hvPlotAgent`) and paths that exist.
- When the ordering logic is a guess from a file name (`dependency.py`), read
  enough of it to confirm, or say in the beat sheet that it is unverified.
- **Check which way every arrow points.** Find the call: if the agents run
  first and hand results to a coordinator, the arrows point in, not out, even
  though the coordinator is the box in the middle. Draw a loop only where the
  code calls back (a tool that re-runs another agent); a pipeline that only
  passes data forward has none.
- Data shown as a result (a chart) is illustrative. Show no numbers on it.

## Story: follow one request

One concrete request traced end to end teaches the architecture better than
describing each box in turn, because every box then appears for a reason.

- Open on the request itself ("Average fare by borough, as a bar chart"),
  with nothing else on screen.
- Use the smallest request that touches every box: two agents, one tool call,
  one LLM call each.
- End the trace where the user sees the result, so the loop closes.

## Layout: a fixed stage

Use a fixed stage with a bus rather than a mindmap. A mindmap shows grouping;
an explainer shows flow, and flow reads best when nothing moves except the
data.

- **Every box has a reserved position for the whole video**, and none is ever
  rearranged to make room. The viewer's spatial memory carries the map.
- **The shared state is a horizontal bus along the bottom**, the largest
  shape on screen. Agents send tokens down to it and lift tokens up from it.
- **Services (LLM, tools) sit in a rack on one side.** A short arc out and
  back reads as "uses", not as a step in the flow.
- **Workers sit in a middle row in plan order**, left to right.
- **One color per kind of thing** for the whole video: workers, services,
  data tokens. Use the accent color only for data in the bus.

## Progressive disclosure

Nothing appears before it is needed, and every appearance has a cause on
screen.

- **One new concept per beat.** The request, then the planner, then one
  worker, then the LLM, then tools, then the bus, then the second worker.
- **Reveal by need.** The LLM slot slides in because the agent needs a model;
  the bus draws in when the agent reaches for its data source. A box never
  appears because it is next on a list.
- **Transform instead of cutting.** Plan cards become agent boxes in place.
- **The second worker introduces nothing.** It reuses the LLM and the bus,
  which is what makes the pattern click.
- **Dim what is idle** to about 30%, and keep it visible.
- **Brighten everything at once only near the end**, as the payoff the viewer
  has built up one piece at a time.

## Labels and captions

- **Boxes show the class name, then its path** in mono a beat later, so text
  never lands with a shape (`SQLAgent`, then `ai/agents/sql.py`).
- **No code on screen.** The path is the takeaway; code at readable size
  needs a zoom that loses the map.
- **One caption at a time**, in a fixed band between the agent row and the
  bus, about 40 px, one plain sentence the viewer can check against what is
  moving.
- State the rule the architecture depends on in so many words near the end
  ("Agents never call each other. They only talk through Context.").

## Pacing

- **Up to 3 minutes**, with about 10–15 s per beat: roughly 1 s for the
  change, then a hold long enough to read the caption and watch the token.
- **One movement at a time.** A token travels, then the next thing happens.
- Keep idle boxes breathing slightly (±1% scale on a slow sine) so a hold
  doesn't read as a frozen frame.

## Ending: where your code goes

Close on the same stage with ghost slots (dashed outlines) in the reserved
gaps, each labeled with the directory a contributor would add to:
`your agent → ai/agents/`, `your tool → ai/tools/`. One line per extension
point, and only extension points the source actually supports. Hold the final
frame at least 3 s.
