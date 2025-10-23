import os, time, random, subprocess, threading, psutil, requests, pathlib
from requests.auth import HTTPBasicAuth
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yt_dlp

# ==== DEFAULT CONFIG ====
BASE_AD_FOLDER = r"C:\StremioAds"
PLAYER_PATH    = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
VLC_PORT       = 8080
VLC_PASS       = "ads"

AD_MIN, AD_MAX   = 120, 180      # 2–3 min per ad break
MID_MIN, MID_MAX = 600, 720      # 10–12 min between mid-rolls (TV)
MOVIE_MID        = 900           # 15 min between mid-rolls (Movie)
HTTP_TIMEOUT     = 2.0
POLL_INTERVAL    = 1.0
YTDLP_RETRIES    = 4

ad_player_pids: set[int] = set()
skip_flag = threading.Event()     # <-- NEW: signal to abort an ad break immediately

# ==== YouTube Playlists ====
YOUTUBE_PLAYLISTS = {
    "70s": ["https://www.youtube.com/playlist?list=PL6475244FE97F6743"],
    "80s": [
        "https://www.youtube.com/playlist?list=PLC3458763E3A3C5A2",
        "https://www.youtube.com/playlist?list=PL6676FB688D404E2A"
    ],
    "90s": [
        "https://www.youtube.com/playlist?list=PL0E12D3DB9229B41D",
        "https://www.youtube.com/playlist?list=PLHFkOmjtjZY5QfyIKHNKSdhyBCQQNm0Tj"
    ],
    "2000s": [
        "https://www.youtube.com/playlist?list=PLhOgAOZC_BOjOa47fN3KxuKr7Ck_4nS5K",
        "https://www.youtube.com/playlist?list=PLYumrCRePE57sGoPoRY14Xdcr9R9DTQpE"
    ],
    "Halloween": [
        "https://www.youtube.com/playlist?list=PL_5uHM6q0J0B-2DnYdnTiPo2ikQPDRxTg",
        "https://www.youtube.com/playlist?list=PLoDl-KRzLg9ZSdFT_1zh4SMgV1h7qQM8i"
    ],
    "Adult Swim": [
        "https://www.youtube.com/playlist?list=PLwgVf5Dv4cTAN1o4ih2w6XdA3A5dv-jLS",
        "https://www.youtube.com/playlist?list=PLeUmP68pUNVJYjWTZMbxjLWfJqqaSsV8_",
        "https://www.youtube.com/playlist?list=PL7dFQnBqZOQv_9yEj6KUtaRBOJ6eyoRJA"
    ]
}

# ==== VLC HTTP ====
def _url(port, path): return f"http://127.0.0.1:{port}{path}"

def _req(path, port, pw, params=None):
    try:
        return requests.get(_url(port, path), params=params,
                            auth=HTTPBasicAuth("", pw), timeout=HTTP_TIMEOUT)
    except requests.RequestException:
        return None

def vlc_ready(port, pw, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = _req("/requests/status.json", port, pw)
        if r and r.ok:
            return True
        time.sleep(0.3)
    return False

def vlc_cmd(port, pw, cmd, val=None):
    p = {"command": cmd}
    if val is not None:
        p["val"] = val
    _req("/requests/status.json", port, pw, p)

def vlc_status(port, pw):
    r = _req("/requests/status.json", port, pw)
    if not (r and r.ok):
        return None
    try:
        return r.json()
    except Exception:
        return None

def vlc_time(port, pw):
    s = vlc_status(port, pw)
    if not s:
        return None
    return s.get("time", None)

def ensure_fullscreen(port, pw, desired=True):
    s = vlc_status(port, pw)
    if not s:
        return
    is_fs = bool(s.get("fullscreen", False))
    if desired and not is_fs:
        vlc_cmd(port, pw, "fullscreen")

# ==== Skip Ads ====
def skip_ads(port=None, pw=None):
    """Immediately terminate all current ad players, abort the ad loop, and resume main playback."""
    global ad_player_pids, skip_flag
    skip_flag.set()  # tell play_ad_break to stop
    print("[ads] Skipping all current ads...")

    for pid in list(ad_player_pids):
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        ad_player_pids.discard(pid)

    # Resume main VLC playback
    if port and pw:
        try:
            vlc_cmd(port, pw, "pl_forceresume")
            ensure_fullscreen(port, pw, True)
            print("[ads] Resumed main playback after skipping ads.")
        except Exception as e:
            print(f"[ads] Could not resume playback: {e}")

# ==== YouTube (no-lua) Direct Stream Resolve ====
def _ydl_for_playlist():
    return yt_dlp.YoutubeDL({
        "quiet": True, "skip_download": True,
        "extract_flat": True, "cachedir": False, "retries": 3,
    })

def _ydl_for_video():
    return yt_dlp.YoutubeDL({
        "quiet": True, "skip_download": True,
        "extract_flat": False, "noplaylist": True,
        "cachedir": False, "retries": 3, "geo_bypass": True,
        "extractor_args": {
            "youtube": {"player_client": ["android", "android_creator", "web_creator"]}
        }
    })

def resolve_random_stream_from_playlists(decade: str):
    dec = decade if decade in YOUTUBE_PLAYLISTS else random.choice(list(YOUTUBE_PLAYLISTS.keys()))
    plists = list(YOUTUBE_PLAYLISTS[dec])
    random.shuffle(plists)

    for _ in range(YTDLP_RETRIES):
        if not plists:
            break
        playlist_url = plists[0]
        print(f"[yt] Using playlist: {playlist_url}")
        try:
            with _ydl_for_playlist() as ypl:
                pli = ypl.extract_info(playlist_url, download=False)
                entries = pli.get("entries", []) if pli else []
        except Exception as e:
            print(f"[yt] playlist read error: {e}")
            plists.append(plists.pop(0))
            continue
        if not entries:
            plists.append(plists.pop(0))
            continue
        random.shuffle(entries)
        for ent in entries[:10]:
            vid = ent.get("id")
            if not vid:
                continue
            watch = f"https://www.youtube.com/watch?v={vid}"
            try:
                with _ydl_for_video() as yv:
                    vi = yv.extract_info(watch, download=False)
            except Exception as e:
                print(f"[yt] video resolve failed ({vid}): {e}")
                continue
            best = None
            for f in vi.get("formats", []):
                if f.get("url") and f.get("protocol") in ("m3u8_native", "https", "http"):
                    best = f
                    break
            if not best:
                continue
            stream_url = best["url"]
            headers = vi.get("http_headers") or {}
            headers.setdefault("User-Agent",
                               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            headers.setdefault("Referer", "https://www.youtube.com/")
            dur = int(vi.get("duration") or 0)
            start = random.randint(0, max(1, dur - 30)) if dur > 60 else 0
            print("[yt] got direct stream")
            return stream_url, headers, start
        plists.append(plists.pop(0))
    return None, None, None

# ==== Ads ====
def play_ad(vlc_path, source, headers=None, start_seconds=0):
    cmd = [
        vlc_path, "--no-one-instance", "--no-playlist-enqueue",
        "--no-video-title-show", "--play-and-exit",
        "--fullscreen", "--video-on-top",
    ]
    if start_seconds > 0:
        cmd.append(f"--start-time={int(start_seconds)}")
    if headers:
        ua = headers.get("User-Agent")
        ref = headers.get("Referer") or headers.get("Referrer")
        if ua: cmd.append(f":http-user-agent={ua}")
        if ref: cmd.append(f":http-referrer={ref}")
    cmd.append(source)
    print(f"[ads] Playing: {source}")
    proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
    ad_player_pids.add(proc.pid)
    return proc

def play_ad_break(folder, vlc_path, decade="90s", first_break=False):
    """Play 2–3 minutes of ads. Aborts immediately if skip_flag is set."""
    global skip_flag
    skip_flag.clear()  # reset at the start of each ad break

    local_ads = []
    if os.path.isdir(folder):
        local_ads = [f for f in os.listdir(folder)
                     if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))]
    use_youtube = (len(local_ads) == 0)

    if first_break and local_ads:
        print("[ads] found local files:", local_ads)

    total = 0.0
    print("[ads] Starting ad break (2–3 min)")

    while total < AD_MIN and not skip_flag.is_set():
        if use_youtube:
            src, hdrs, start = resolve_random_stream_from_playlists(decade)
            if not src:
                print("[ads] unable to resolve YouTube stream; stopping break")
                break
            p = play_ad(vlc_path, src, headers=hdrs, start_seconds=start)
        else:
            ad = random.choice(local_ads)
            src = os.path.join(folder, ad)
            p = play_ad(vlc_path, src)

        # Run the current ad, but stop if user presses Skip or we hit AD_MAX
        while p.poll() is None and total < AD_MAX and not skip_flag.is_set():
            time.sleep(0.25)
            total += 0.25

        # Stop current ad process if still alive
        try:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=2)
        except Exception:
            try: p.kill()
            except Exception: pass

        ad_player_pids.discard(p.pid)

        if skip_flag.is_set():
            print("[ads] Ad break aborted by user skip.")
            break

        # If we reached AD_MAX naturally, end this ad break immediately
        if total >= AD_MAX:
            print("[ads] Reached hard cap; ending ad break.")
            break

    print(f"[ads] End of ad break ({int(total)}s)\n")

# ==== Process watch ====
def detect_new_vlc_pid(known):
    current = {p.pid for p in psutil.process_iter(["name"])
               if p.info["name"] and p.info["name"].lower() in ("vlc.exe","vlc")
               and p.pid not in ad_player_pids}
    new = list(current - known)
    return new[0] if new else None

def wait_exit(pid):
    try:
        proc = psutil.Process(pid)
    except psutil.Error:
        return
    while proc.is_running():
        time.sleep(0.5)

# ==== Episode lifecycle ====
def run_episode(pid, cfg):
    folder, port, pw, vlc_path, decade, watch_type = (
        cfg["ad_folder"], cfg["http_port"], cfg["http_pass"],
        cfg["vlc_path"], cfg["decade"], cfg["type"]
    )
    print(f"[core] Detected show PID {pid}")
    if not vlc_ready(port, pw, 20):
        raise RuntimeError("VLC web interface not reachable.")

    # Pre-roll
    vlc_cmd(port, pw, "pl_forcepause")
    vlc_cmd(port, pw, "seek", "0")
    play_ad_break(folder, vlc_path, decade, first_break=True)
    vlc_cmd(port, pw, "pl_forceresume")
    ensure_fullscreen(port, pw, True)

    # Mid-roll schedule
    if watch_type == "Movie":
        mid_min = mid_max = MOVIE_MID
    else:
        mid_min, mid_max = MID_MIN, MID_MAX

    next_break = random.randint(mid_min, mid_max)
    print(f"[core] Next mid-roll in {next_break // 60} min")

    idle_counter = 0
    while psutil.pid_exists(pid):
        status = vlc_status(port, pw)
        if not status:
            time.sleep(POLL_INTERVAL)
            continue

        state = status.get("state", "")
        time_pos = status.get("time", 0)

        # Mid-roll trigger
        if state == "playing" and time_pos and time_pos >= next_break:
            print("[core] Mid-roll triggered")
            vlc_cmd(port, pw, "pl_forcepause")
            play_ad_break(folder, vlc_path, decade)
            vlc_cmd(port, pw, "pl_forceresume")
            ensure_fullscreen(port, pw, True)
            next_break += random.randint(mid_min, mid_max)
            print(f"[core] Next mid-roll in {(next_break - time_pos) // 60} min")

        # End detection
        if state in ("stopped", "ended"):
            idle_counter += 1
        else:
            idle_counter = 0

        if idle_counter > 4:
            print("[core] Playback finished (VLC idle). Running post-roll ads...")
            play_ad_break(folder, vlc_path, decade)
            print("[core] Post-roll ads complete. Done!\n")
            return

        time.sleep(POLL_INTERVAL)

    print("[core] VLC closed unexpectedly, no post-roll triggered.\n")

# ==== Watcher thread ====
def watcher(stop_event, cfg, log):
    known = set()
    log("Watching for new VLC windows...")
    while not stop_event.is_set():
        pid = detect_new_vlc_pid(known)
        if pid:
            known.add(pid)
            time.sleep(1)
            try:
                run_episode(pid, cfg)
                wait_exit(pid)
            except Exception as e:
                log("Error: " + str(e))
        else:
            time.sleep(0.5)

# ==== GUI ====
class GUI:
    def __init__(self, root):
        self.root = root
        root.title("VLC Ad Scheduler")
        root.geometry("580x430")
        root.resizable(False, False)
        f = ttk.Frame(root)
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ttk.Label(f, text="Ad Folder:").grid(row=0, column=0, sticky="w")
        self.ad_var = tk.StringVar(value=BASE_AD_FOLDER)
        ttk.Entry(f, textvariable=self.ad_var, width=42).grid(row=0, column=1, sticky="w")
        ttk.Button(f, text="Browse…", command=self.browse_ads).grid(row=0, column=2, padx=5)

        ttk.Label(f, text="Ad Decade:").grid(row=1, column=0, sticky="w")
        self.decade_var = tk.StringVar(value="90s")
        ttk.Combobox(f, textvariable=self.decade_var,
                     values=list(YOUTUBE_PLAYLISTS.keys()),
                     width=10, state="readonly").grid(row=1, column=1, sticky="w")

        ttk.Label(f, text="Watching Type:").grid(row=2, column=0, sticky="w")
        self.type_var = tk.StringVar(value="Show")
        ttk.Combobox(f, textvariable=self.type_var,
                     values=["Show", "Movie"],
                     width=10, state="readonly").grid(row=2, column=1, sticky="w")

        ttk.Label(f, text="VLC Path:").grid(row=3, column=0, sticky="w")
        self.vlc_var = tk.StringVar(value=PLAYER_PATH)
        ttk.Entry(f, textvariable=self.vlc_var, width=42).grid(row=3, column=1, sticky="w")

        ttk.Label(f, text="VLC HTTP Port:").grid(row=4, column=0, sticky="w")
        self.port_var = tk.StringVar(value=str(VLC_PORT))
        ttk.Entry(f, textvariable=self.port_var, width=10).grid(row=4, column=1, sticky="w")

        ttk.Label(f, text="VLC HTTP Password:").grid(row=5, column=0, sticky="w")
        self.pass_var = tk.StringVar(value=VLC_PASS)
        ttk.Entry(f, textvariable=self.pass_var, width=14, show="•").grid(row=5, column=1, sticky="w")

        self.start_btn = ttk.Button(f, text="▶️ Start", command=self.start_w)
        self.stop_btn  = ttk.Button(f, text="⏹ Stop", command=self.stop_w, state="disabled")
        self.skip_btn  = ttk.Button(f, text="⏭ Skip Ads", command=self.skip_ads_pressed, state="disabled")

        self.start_btn.grid(row=6, column=0, pady=8)
        self.stop_btn.grid(row=6, column=1, sticky="w", pady=8)
        self.skip_btn.grid(row=6, column=2, sticky="w", pady=8)

        self.status = tk.Label(f, text="Stopped", fg="red")
        self.status.grid(row=7, column=0, columnspan=3, sticky="w")
        self.log = tk.Text(f, height=10, width=70, state="disabled")
        self.log.grid(row=8, column=0, columnspan=3, pady=6)

        for i in range(3):
            f.grid_columnconfigure(i, weight=1)
        self.thread = None
        self.stop_ev = None

    def browse_ads(self):
        folder = filedialog.askdirectory(title="Select Ad Folder", initialdir=self.ad_var.get())
        if folder:
            self.ad_var.set(folder)

    def logw(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def start_w(self):
        ads = self.ad_var.get().strip()
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Error", "Port must be a number.")
            return
        cfg = {
            "ad_folder": ads,
            "http_port": port,
            "http_pass": self.pass_var.get(),
            "vlc_path": self.vlc_var.get(),
            "decade": self.decade_var.get(),
            "type": self.type_var.get(),
        }
        self.stop_ev = threading.Event()
        self.thread = threading.Thread(target=watcher, args=(self.stop_ev, cfg, self.logw), daemon=True)
        self.thread.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.skip_btn.config(state="normal")
        self.status.config(text="Running", fg="green")
        self.logw(f"Watching VLC... (ads: local folder or {self.decade_var.get()} YouTube playlists, {self.type_var.get()} mode)")

    def stop_w(self):
        if self.stop_ev:
            self.stop_ev.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.skip_btn.config(state="disabled")
        self.status.config(text="Stopped", fg="red")
        self.logw("Stopped.")

    def skip_ads_pressed(self):
        try:
            port = int(self.port_var.get())
        except ValueError:
            port = VLC_PORT
        pw = self.pass_var.get()
        skip_ads(port, pw)
        self.logw("User skipped ads — playback resumed.")

def main():
    root = tk.Tk()
    GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
