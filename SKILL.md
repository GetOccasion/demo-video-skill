---
name: demo-video
description: Produce a narrated, subtitled screen-recorded demo video of a web app feature — scripted browser interactions recorded with agent-browser, a local Kokoro voiceover, and subtitles burned in with ffmpeg. Use whenever the user wants a demo video, walkthrough, screencast, feature tour, explainer or recorded demo of something in their app, wants to "show" a feature to a team, customers or stakeholders as a video, or asks for a voiceover or subtitles on a recording — even if they don't say "skill" or name any of these tools.
---

# Demo video

Turns a feature into a short video: real interactions in a real browser, a voiceover that explains what is on screen, and subtitles. Everything runs locally: agent-browser records, Kokoro speaks, ffmpeg and Pillow assemble.

The one idea that makes it work: **the narration is the clock.** Render the voiceover first, measure every scene, and cue each browser action to the word that talks about it. Never time narration to a recording; a recording's pace drifts, a WAV's doesn't. The recording itself doesn't wait for the narration: actions run back to back, and assembly freezes the frame wherever the narration needs more time.

## Tools

This skill's scripts sit in `scripts/` under its base directory, the one shown as "Base directory for this skill" when it loaded; the example scenario sits in `references/` there. Each shell command starts afresh, so a variable exported in one is gone in the next: start every command that needs them with `export SCRIPTS=<base directory>/scripts DEMO=<demo directory>;` (below), as here for the preflight:

```bash
export SCRIPTS=<base directory>/scripts; bash $SCRIPTS/preflight.sh
```

It checks for `agent-browser` and a Chrome for it, `ffmpeg`/`ffprobe` with libx264, and Kokoro's Python environment and model: either preinstalled (`DEMO_VIDEO_VENV` is set), or `uv` (which runs Kokoro and Pillow on Python 3.12 whatever the system Python is) plus access to Hugging Face. **If it exits non-zero, stop**: tell the user what is missing and how to install it, and don't start on the script, the data or the recording. Don't substitute another TTS engine, recorder or a silent video without asking — the result would not be what they asked for. Its warnings (no `espeak-ng`, no system font) don't block; mention them.

`$SCRIPTS/python` runs the Python scripts below on the environment the skill's `uv.lock` pins; scenarios read `$SCRIPTS` too. Keep all working files in one demo directory (`DEMO`, an absolute path) in the scratchpad, outside the repository. If you can write only inside the repository, or the video is to be attached to a pull request from there, use a folder in it that git ignores instead: `tmp/demo-video/<name>` when `git check-ignore -q tmp/demo-video` succeeds, otherwise another folder it confirms is ignored, so nothing in it can be committed. Don't edit `.gitignore` for this without asking.

## Workflow

### 1. Understand the feature and pick the story

Read the branch diff, the plan or PR description and the feature's user-facing copy (i18n files, tooltips, help text). The tooltips usually define the columns and options better than anything else — the narration should agree with them word for word on what a number means.

Pick a protagonist (a fictional business that would really use the feature) and a question the feature answers for them. A demo that walks one concrete scenario from question to answer beats a tour of every control.

Ask the user only what changes the video: audience (customers or the team), target length, voice, and whether they want to read the script before anything is recorded. Defaults: customers, ~3 minutes, `af_heart`. Skip the questions they have already answered or made moot — someone who asked for the whole thing end to end without check-ins, or who is clearly not around to answer, gets the defaults and no script review.

### 2. Make demo data that tells the story

Empty or random data makes a feature look broken. Build data whose numbers make each point on screen obvious: edge cases visible on the first screen, totals that change visibly when an option flips.

- **Isolate it.** Seed a separate database, and run the app on its own port; never reuse the user's dev data. Look for the project's own conventions first (CLAUDE.md, guides on worktrees and dev servers, seed directories). If the project has a seed framework, write a reusable, per-industry demo seed in it (e.g. `db/seeds/demos/bike_shop.rb`) rather than a one-off script — the next demo then costs nothing. Ask before committing it.
- **Date everything relative to today**, so the demo never goes stale.
- **History needs time travel.** Apps refuse to create orders or bookings in the past; create each record at the moment it would really have been created (e.g. Rails `travel_to`). Watch for state that ignores the travelled clock: values memoized on an instance loaded before travelling, and status columns computed at creation. Reload and refresh them inside the travel block.
- **Snapshot the empty schema** (e.g. `createdb -T`) so reseeding after a fix is a drop-and-copy, not a migration.
- Then open the page and check every number you plan to mention.

### 3. Write the script

Write `DEMO/scenes.json`: `[{"id": "01_intro", "text": "..."}, ...]`. One scene per idea, 10–15 scenes. Ids sort in playing order.

- **Length:** Kokoro speaks at ~150 words per minute, and each scene adds ~1–3 s of actions and pauses. For 3 minutes, write about 450 words; 420 words came out at 2:40.
- Say what the viewer is looking at, in the order they see it. Name controls by their on-screen label.
- Write for the ear: short sentences, numbers spelled out where they read oddly ("twenty-five percent").
- Follow the project's vocabulary rules (glossaries, reserved words) in the narration as in code.
- **Name what is on screen, when it is on screen.** Don't name a filter value, menu option or record before the viewer can see it ("everything Sam sold" while the staff list is still closed). Put the menu-opening words before the name, so the scenario can open the menu first and land the pointer on the option as it is spoken.
- **Open with the feature's own question.** The first sentence must be one only this feature answers. "How much did we sell this month?" also describes a neighbouring report; "Which store sold the most starter kits?" does not. Check the app's sibling features (other reports, other settings pages) before settling on it.
- **Write for the stated audience.** A customer demo shows what they can do; an internal demo for marketing or account management also covers how it decides things, how to turn it on, its limits, and what to tell a customer who asks.

**If the user asked to review the script**, stop here and show it before rendering audio: a short outline first (one line per scene: what is shown and the one claim it makes), plus any claims you are unsure of, with the full text below for those who want it. Changing a sentence later means re-rendering that scene, re-cueing the scenario and re-recording the take, so this is the cheapest moment to change the story. Otherwise carry on; mention in the final report that the script is in `DEMO/scenes.json`.

### 4. Render the voiceover

```bash
export SCRIPTS=… DEMO=…; bash $SCRIPTS/python $SCRIPTS/narrate.py $DEMO
```

Writes `tts/<id>.wav` and `tts/<id>.words.json` with per-word timestamps, and prints each scene's length. Re-render single scenes with `--only <id> ...`. Voices: `af_heart` (most natural US), `am_michael`, `bf_emma` (British). The first letter of the voice picks the language.

### 5. Dry-run every interaction

Before recording, drive each step once with `agent-browser` and take a screenshot. This finds what will break on camera: wrong routes, elements covered by overlays, menus that submit on close, a layout that shifts when a badge appears. Snapshot refs (`@e12`) change on every page load, so use stable CSS selectors (ids, `dom_id`s, `name=`) in the scenario. Prefer them over `demo.click_role`: the helpers glide the pointer to a selector's element before acting, but agent-browser gives no position for a role, so a role click makes the pointer jump.

Hide dev-only overlays (profilers, debug bars) and clear one-time flashes such as "Logged in as…" by loading the page twice before the take starts (`demo.prime(url)`).

### 6. Write the scenario and record

A scenario is a short Python script in `DEMO` using `SCRIPTS/recorder.py`. Start from `references/example_scenario.py`. Cue actions to words with `s.at("word")`. Punctuation is its own token, so cue `"October"` and not `"October,"`, and use `nth=` when a word appears twice.

**Move only through the helpers.** Raw `agent-browser` pointer commands teleport the pointer and a mouse wheel jumps the page, which reads as a cut on camera. `demo.move`, `demo.hover` and `demo.click` glide the pointer there and return once it has arrived; `demo.scroll` animates the scroll and returns once the page is still. So every motion is on the recording in full, before the next hold freezes a frame.

**Let the viewer read every menu.** A list that opens and closes within a second shows nothing. Use the helpers, which dwell on the open list and rest the pointer on the option before choosing it:

- `demo.pick(open_trigger, option_selector)` for custom HTML menus.
- Pass `scene=s, cue="<word>"` to either helper to land the pointer on the option exactly when the narrator names it; the menu opens about two seconds before. That needs two seconds of narration before the cue word in the same scene, with no slow action in between — assembly prints `warning: … runs …s late` when it can't, and the fix is in the script ("The third choice in that menu splits it…" rather than "Or split it…") or in moving the slow action to the previous scene.
- `demo.pick_native(select_selector, label)` for a native `<select>`. A headless recording never draws a native select's popup, so this draws a stand-in list from the select's real options, points at the choice, then selects it.

**One viewport per take.** A take whose viewport changes mid-recording comes out distorted. Record a phone segment as its own take (`demo.viewport(390, 844)`); assembly fits it onto a canvas. A short closing take after it returns to desktop.

Record each take: `export SCRIPTS=… DEMO=…; python3 -I $DEMO/scenario.py desktop` (and `phone`, `outro`, …). Recording is untimed: `s.at()` and `s.until()` don't sleep but log a hold point, so the take runs only as long as its actions do (a 2-minute video records in under a minute) and a broken selector or a cue word missing from the narration fails within seconds. That makes a separate dry run unnecessary; iterate on takes directly. Each take writes `<take>.mp4` and `<take>.holds.json`; assembly freezes the frame at each hold point until the narration reaches its cue word. If a step fails mid-take, fix the scenario and re-run the whole take; the holds must come from a clean run.

Every action must leave the page settled before the next cue, since that last frame is what gets frozen: keep the `time.sleep` after a reload or a menu that submits, or a held frame shows a half-loaded page. Anything that runs on its own clock (a toast that fades, a spinner, a countdown) only advances while the scenario is acting, so a hold freezes it mid-way. To keep one off camera, settle until it has finished before the next cue, as `prime` does for login notices. To show one, such as a "Saved" toast appearing and fading, put a `time.sleep` after the action that covers the whole effect, so it plays out before the next hold. For a page that animates continuously while idle, record that take timed with `DEMO_TIMED=1`, which sleeps until each cue word while recording and writes `<take>.timeline.json` instead.

### 7. Assemble

Close the browser first (`agent-browser close`): Chrome and ffmpeg's encoder together can outgrow a small machine's or container's memory.

```bash
export SCRIPTS=… DEMO=…; bash $SCRIPTS/python $SCRIPTS/assemble.py $DEMO --takes desktop phone outro --out <name>
```

Produces `DEMO/build/<name>.mp4` with burned-in subtitles, a soft subtitle track and narration, plus `<name>.srt`.

### 8. Review before handing over

You can see the video but you can't hear it. Check what you can:

```bash
export DEMO=…; ffmpeg -v error -y -i $DEMO/build/<name>.mp4 -vf "fps=1/6,scale=480:-1,tile=4x8" -frames:v 1 $DEMO/build/grid.png   # read it
export DEMO=…; ffmpeg -i $DEMO/build/<name>.mp4 -map 0:a -af volumedetect -f null - 2>&1 | grep volume                              # not silent
```

In the grid, confirm that every scene shows what its narration describes, the subtitles never cover the thing being pointed at, and no frame catches a half-loaded page or an error. Grab single frames at the cue times (`-ss <t>`) for the moments that matter.

Then stop the dev server and hand the video over: on the user's own machine, copy it somewhere they can find it and `open` it; elsewhere, give its path, or attach it to the pull request if a tool of yours does that. When you report back, say what you could not verify (audio by ear) and list any shortcuts taken, such as a stand-in menu.

## Pitfalls already paid for

- `agent-browser click` fails with "covered by" while a page still settles. `recorder.ab` retries; a failure that survives the retries is real, so fix the selector.
- Menus that submit when they close, such as checklists that submit on Escape, take a few seconds to reload. Wait for that before the next click, or that click lands on a moved button.
- Overmind refuses to start over a stale `.overmind.sock`. Remove the socket only after confirming nothing answers on it (`overmind status`).
- Long scratchpad paths overflow Unix socket limits; don't point sockets there.
- Kokoro splits long text into chunks; `narrate.py` offsets each chunk's word timestamps, so cue by word, never by guessed seconds.
