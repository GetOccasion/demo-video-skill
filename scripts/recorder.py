"""Records a scripted browser demo with agent-browser, cueing every action to its narration.

Import it from a scenario script:

    import sys, os
    sys.path.insert(0, os.environ["SCRIPTS"])
    from recorder import Demo

    demo = Demo(workdir="/path/to/demo")          # holds tts/<scene>.wav and tts/<scene>.words.json
    demo.viewport(1440, 900)
    demo.prime("http://localhost:3000/reports")     # load twice: clears login flashes before recording
    with demo.take("desktop") as take:
        with take.scene("01_intro") as s:
            s.at("report")                          # wait until the narrator says "report..."
            demo.click("a[href*='report']")

Modes, picked by environment variable:
- untimed (default): actions run back to back while recording. Each cue is logged as a hold point in
  <take>.holds.json, and assemble.py freezes the frame there until the narration reaches the cue word.
- DEMO_TIMED=1: sleeps until each cue word while recording and writes <take>.timeline.json
  (scene -> start seconds). For pages that animate while idle, where a frozen frame would show.
"""
import json
import os
import subprocess
import time
from pathlib import Path

PAUSE_AFTER_SCENE = 1.2   # breathing room after each scene's narration ends
LEAD = 0.25               # the recorder starts a beat after `record start` returns
TIMED = os.environ.get("DEMO_TIMED") == "1"
# An action's command returns before the browser has painted its result; the frame frozen at a hold must show it.
PAINT_SETTLE = 0.15

GLIDE_MS = 600            # how long the pointer takes to travel to its next target
SCROLL_MS = 700           # how long a scroll animates

# A viewer needs time to read a list before the pointer picks from it.
MENU_OPEN_DWELL = 1.4     # list visible, pointer still on the trigger
OPTION_HOVER_DWELL = 1.0  # pointer resting on the option about to be chosen
AFTER_PICK_DWELL = 0.6


class BrowserError(RuntimeError):
    pass


def ab(*args, check=True, attempts=4):
    """Runs one agent-browser command. Retries, because clicks fail while the layout is still shifting."""
    for _ in range(attempts):
        result = subprocess.run(["agent-browser", *map(str, args)], capture_output=True, text=True)
        out = (result.stdout + result.stderr).strip()
        if "✗" not in out and result.returncode == 0:
            return out
        time.sleep(0.8)
    if check:
        raise BrowserError(f"agent-browser {' '.join(map(str, args))}: {out}")
    return out


class Scene:
    def __init__(self, take, scene_id):
        self.take, self.id = take, scene_id
        tts = take.demo.workdir / "tts"
        self.words = json.loads((tts / f"{scene_id}.words.json").read_text())
        self.length = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(tts / f"{scene_id}.wav")],
            capture_output=True, text=True, check=True).stdout)

    def __enter__(self):
        self.t0 = time.monotonic()
        self.take.timeline[self.id] = self.take.video_time()
        self.take.holds.append({"scene": self.id, "start": self.take.video_time()})
        return self

    def cue_time(self, word, nth=0):
        """Seconds into the scene at which the narrator starts the nth word beginning with `word`."""
        hits = [w for w in self.words if w["w"].strip().lower().startswith(word.lower())]
        if len(hits) <= nth:
            raise ValueError(f"{self.id}: no occurrence {nth} of {word!r} in the narration")
        return hits[nth]["s"]

    def at(self, word, offset=0.0, nth=0):
        """Waits until the narration reaches the nth word starting with `word` (punctuation is its own token)."""
        self.until(self.cue_time(word, nth) + offset)

    def until(self, seconds):
        """Lets the narration reach `seconds` into the scene: a sleep when timed, a logged hold point otherwise."""
        if not TIMED:
            time.sleep(PAINT_SETTLE)
            self.take.holds.append({"scene": self.id, "at": self.take.video_time(), "until": seconds})
            return
        delay = self.t0 + LEAD + seconds - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.until(self.length + PAUSE_AFTER_SCENE)


class Take:
    def __init__(self, demo, name):
        self.demo, self.name, self.timeline, self.holds = demo, name, {}, []

    def __enter__(self):
        ab("record", "start", self.demo.workdir / f"{self.name}.mp4", "--cursor")
        self.start = time.monotonic()
        if not TIMED:
            time.sleep(0.5)
            self.sync = [self.flash()]
        return self

    def flash(self):
        """Shows a full-screen magenta frame, the clapperboard assemble.py aligns this take's clock to.

        The recording's own clock runs ahead of the wall clock by a fraction of a second, enough to freeze the start
        of the next action. Two flashes, one at each end, map every logged time onto the video.
        """
        ab("eval", "(() => { const d = document.createElement('div'); d.id = '__demo_sync'; "
                   "d.style.cssText = 'position:fixed;inset:0;background:#f0f;z-index:2147483647'; "
                   "document.body.appendChild(d); })()")
        at = self.video_time()
        time.sleep(0.4)
        ab("eval", "document.getElementById('__demo_sync')?.remove()")
        time.sleep(0.4)
        return at

    def video_time(self):
        """Seconds into the recording at this moment."""
        return time.monotonic() - self.start + LEAD

    def scene(self, scene_id):
        return Scene(self, scene_id)

    def __exit__(self, exc_type, *_):
        if not TIMED and exc_type is None:
            self.sync.append(self.flash())
        time.sleep(0.5)
        ab("record", "stop")
        if exc_type:
            return
        timeline, holds = (self.demo.workdir / f"{self.name}.{kind}.json" for kind in ("timeline", "holds"))
        if TIMED:
            timeline.write_text(json.dumps(self.timeline, indent=1))
            holds.unlink(missing_ok=True)
        else:
            holds.write_text(json.dumps({"sync": self.sync, "holds": self.holds}, indent=1))
            timeline.unlink(missing_ok=True)
        print(f"recorded {self.name} in {time.monotonic() - self.start:.0f}s")


class Demo:
    def __init__(self, workdir):
        self.workdir = Path(workdir)

    def take(self, name):
        return Take(self, name)

    # -- page ---------------------------------------------------------------------------------

    def viewport(self, width, height):
        ab("set", "viewport", width, height)

    def open(self, url, settle=1.5):
        ab("open", url)
        time.sleep(settle)

    def prime(self, url):
        """Opens the page twice so one-time flashes (login notices, cookie banners) are gone on camera.

        The second load settles long enough for a fading toast to finish, since a take's first frame may be held.
        """
        self.open(url)
        self.open(url, settle=3.0)

    # -- pointer ------------------------------------------------------------------------------
    # agent-browser teleports the pointer unless a move has --steps, and a teleport reads as a jump on camera.
    # So every pointer action glides to its target first, and returns only once the pointer has arrived.

    def click(self, selector):
        self.glide_to(selector)
        ab("click", selector)

    def click_role(self, role, name, exact=False):
        """Clicks by accessible name. The pointer jumps here, as agent-browser gives no position for a role; prefer a
        CSS selector on camera."""
        ab("find", "role", role, "click", "--name", name, *(["--exact"] if exact else []))

    def hover(self, selector, check=True):
        if self.glide_to(selector, check=check):
            ab("hover", selector, check=check)

    def move(self, x, y, duration=GLIDE_MS):
        ab("mouse", "move", x, y, "--duration", duration, "--steps", max(2, min(240, duration // 40)))

    def glide_to(self, selector, check=True):
        """Glides the pointer to the middle of `selector`. Returns False when it isn't on the page and check is off."""
        out = ab("get", "box", selector, "--json", check=check)
        if not out.startswith("{") or not json.loads(out)["success"]:
            return False
        box = json.loads(out)["data"]
        self.move(round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2))
        return True

    def scroll(self, pixels, duration=SCROLL_MS):
        """Scrolls with an eased animation and waits until the page is still. A mouse wheel jumps, or starts
        half-way through its own animation."""
        ab("eval", _SMOOTH_SCROLL_JS % {"pixels": pixels, "duration": duration})
        time.sleep(duration / 1000)
        last = None
        for _ in range(30):
            position = ab("eval", _SCROLL_POSITION_JS)
            if position == last:
                break
            last = position
            time.sleep(0.1)

    def type(self, selector, text, settle=2.0):
        """Clears a field and types into it key by key, so the viewer sees it being typed."""
        self.click(selector)
        ab("fill", selector, "")
        if text:
            ab("keyboard", "type", text)
        time.sleep(settle)

    # -- menus: give the viewer time to read the list -----------------------------------------

    def pick(self, open_trigger, option, settle=2.0, scene=None, cue=None):
        """Opens a custom (HTML) menu, dwells on it, rests the pointer on `option`, then clicks it.

        `open_trigger` is a CSS selector or a callable. `option` is a CSS selector or a
        (role, accessible name) pair, e.g.
        demo.pick(lambda: demo.click_role("button", "Month", exact=True), ("button", "Sep 2026")).
        With `scene` and `cue`, the pointer reaches the option as the narrator says `cue`.
        """
        self._before_cue(scene, cue, MENU_OPEN_DWELL)
        self._do(open_trigger)
        self._dwell_until_cue(scene, cue)
        if isinstance(option, tuple):
            role, name = option
            ab("find", "role", role, "hover", "--name", name, "--exact")
            time.sleep(OPTION_HOVER_DWELL)
            ab("find", "role", role, "click", "--name", name, "--exact")
        else:
            self.hover(option)
            time.sleep(OPTION_HOVER_DWELL)
            self.click(option)
        time.sleep(AFTER_PICK_DWELL + settle)

    def pick_native(self, select, label, settle=2.0, scene=None, cue=None):
        """Chooses `label` in a native <select>, showing its options first.

        A headless recording never draws a native select's popup, so this draws a stand-in list
        from the select's real options under it, rests the pointer on `label`, then selects it.
        """
        self._before_cue(scene, cue, MENU_OPEN_DWELL + 0.4)
        self.hover(select)
        time.sleep(0.4)
        ab("eval", _NATIVE_MENU_JS % {"select": json.dumps(select), "label": json.dumps(label)})
        self._dwell_until_cue(scene, cue)
        self.hover(f"#__demo_select [data-label={json.dumps(label)}]")
        time.sleep(OPTION_HOVER_DWELL)
        ab("eval", "document.getElementById('__demo_select')?.remove()")
        ab("select", select, label)
        time.sleep(settle)

    @staticmethod
    def _before_cue(scene, cue, lead):
        """Waits until `lead` seconds before the narrator says `cue`, so the menu is open by then."""
        if cue:
            hit = scene.cue_time(cue)
            late = time.monotonic() - (scene.t0 + LEAD + hit - lead)
            if TIMED and late > 0.1:
                print(f"warning: {scene.id}: menu for {cue!r} opens {late:.1f}s late; move earlier actions out of the way")
            scene.at(cue, offset=-lead)

    @staticmethod
    def _dwell_until_cue(scene, cue):
        if cue:
            scene.at(cue)
        else:
            time.sleep(MENU_OPEN_DWELL)

    def _do(self, action):
        if isinstance(action, str):
            self.click(action)
        else:
            action()


_SMOOTH_SCROLL_JS = """(() => {
  const scrollable = e => e && /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight;
  let el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  while (el && !scrollable(el)) el = el.parentElement;
  el = el || document.scrollingElement;
  const from = el.scrollTop, to = Math.max(0, Math.min(el.scrollHeight - el.clientHeight, from + %(pixels)d));
  const behavior = el.style.scrollBehavior, start = performance.now();
  el.style.scrollBehavior = 'auto';
  const step = now => {
    const t = Math.min(1, (now - start) / %(duration)d);
    el.scrollTop = from + (to - from) * (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    if (t < 1) requestAnimationFrame(step); else el.style.scrollBehavior = behavior;
  };
  requestAnimationFrame(step);
})()"""

_SCROLL_POSITION_JS = """[document.scrollingElement, ...document.querySelectorAll('*')]
  .filter(e => e.scrollTop > 0).map(e => e.scrollTop).join(',')"""

_NATIVE_MENU_JS = """(() => {
  const select = document.querySelector(%(select)s);
  const box = select.getBoundingClientRect();
  const menu = document.createElement('div');
  menu.id = '__demo_select';
  const style = document.createElement('style');
  style.textContent = '#__demo_select div:hover{background:#6d28d9;color:#fff}';
  menu.appendChild(style);
  const font = getComputedStyle(select).font;
  Object.assign(menu.style, {position: 'fixed', left: box.left + 'px', minWidth: box.width + 'px',
    background: '#fff', border: '1px solid #d1d5db', borderRadius: '10px', padding: '4px 0',
    boxShadow: '0 12px 28px rgba(0,0,0,.18)', zIndex: 2147483646, font,
    maxHeight: Math.min(window.innerHeight - 16, 420) + 'px', overflowY: 'auto'});
  [...select.options].forEach(option => {
    const row = document.createElement('div');
    row.textContent = option.text;
    row.dataset.label = option.text;
    Object.assign(row.style, {padding: '9px 16px', cursor: 'default', whiteSpace: 'nowrap',
      fontWeight: option.selected ? '600' : '400'});
    menu.appendChild(row);
  });
  document.body.appendChild(menu);
  const below = window.innerHeight - box.bottom;
  menu.style.top = (below > menu.offsetHeight + 8 ? box.bottom + 4 : Math.max(8, box.top - menu.offsetHeight - 4)) + 'px';
  const chosen = [...menu.children].find(row => row.dataset && row.dataset.label === %(label)s);
  menu.scrollTop = chosen.offsetTop - menu.clientHeight / 2;
})()"""
