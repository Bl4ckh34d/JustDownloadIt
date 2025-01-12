import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import subprocess
import platform
import time
from pathlib import Path

try:
    from pySmartDL import SmartDL
except ImportError:
    SmartDL = None

try:
    import browser_cookie3 as browsercookie
except ImportError:
    browsercookie = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

version = "0.6"

# Format definitions for YouTube downloads
VIDEO_FORMATS = [
    "2160p (4K)",  # Format 313/401
    "1440p (2K)",  # Format 271/400
    "1080p (HD)",  # Format 137/248/399
    "720p",        # Format 136/247/398
    "480p",        # Format 135/244/397
    "360p",        # Format 134/243/396
    "240p",        # Format 133/242/395
    "144p"         # Format 160/278/394
]

AUDIO_FORMATS = [
    "High (opus)",      # Format 251 (opus webm)
    "High (m4a)",       # Format 140 (m4a)
    "Medium (opus)",    # Format 250 (opus webm)
    "Medium (m4a)",     # Format 139 (m4a)
    "Low (opus)",       # Format 249 (opus webm)
    "Low (m4a)"         # Format 599 (m4a)
]

COMBINED_FORMATS = [
    "Best available",   # Will pick highest resolution available
    "1080p",           # Format 137+251 (best video + best audio)
    "720p",            # Format 136+251
    "480p",            # Format 135+251
    "360p",            # Format 134+251 or Format 18 (already combined)
    "240p",            # Format 133+251
    "144p"             # Format 160+251
]

QUALITY_RANKS = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "ultralow": 0
}

def print_log(message: str):
    log_box.config(state=tk.NORMAL)
    log_box.insert(tk.END, message + "\n")
    log_box.see(tk.END)
    log_box.config(state=tk.DISABLED)

def clear_log():
    log_box.config(state=tk.NORMAL)
    log_box.delete("1.0", tk.END)
    log_box.config(state=tk.DISABLED)

def open_folder(folder: Path):
    system_name = platform.system()
    try:
        if system_name == "Windows":
            os.startfile(folder)  # type: ignore
        elif system_name == "Darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])
    except Exception as e:
        print_log(f"Could not open folder automatically: {e}")

def get_youtube_cookies():
    if browsercookie is None:
        print_log("browser-cookie3 not installed or failed to import; cannot load YouTube cookies.")
        return None
    try:
        # Try to load cookies from multiple browsers
        try:
            cj = browsercookie.chrome(domain_name='.youtube.com')
        except:
            try:
                cj = browsercookie.firefox(domain_name='.youtube.com')
            except:
                cj = browsercookie.load(domain_name='.youtube.com')
        print_log("Successfully loaded YouTube cookies from your browser.")
        return cj
    except Exception as e:
        print_log(f"Could not load YouTube cookies: {e}")
        return None

youtube_streams = {}

def on_format_selected(selected_var, other_vars):
    """
    If the 'Separate AV' checkbox is OFF,
    make sure only one format is chosen by clearing the others.
    """
    if not combine_av_var.get():  # Only enforce mutual exclusivity if checkbox is not checked
        if selected_var.get() != "None":
            for other_var in other_vars:
                other_var.set("None")

def load_youtube_streams():
    lines = get_links_list()
    if len(lines) != 1:
        messagebox.showwarning("Invalid", "Please enter exactly one YouTube link to load streams.")
        return
    url = lines[0]

    if not yt_dlp:
        messagebox.showerror("Error", "yt-dlp not installed or failed to import.")
        return

    try:
        print_log(f"Initializing yt-dlp for URL: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print_log(f"Title: {info.get('title', 'Unknown')}")
            print_log(f"Duration: {info.get('duration', 'Unknown')} seconds")
            
            formats = info.get('formats', [])
            print_log(f"Found {len(formats)} available formats")
            
            combined_streams = []
            videoonly_streams = []
            audioonly_streams = []
            
            # Process all formats
            for f in formats:
                size = f.get('filesize', 0) or f.get('filesize_approx', 0)
                size_mb = size / 1_000_000 if size else 0
                
                # Get format details
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                ext = f.get('ext', 'unknown')
                format_id = f.get('format_id', 'unknown')
                format_note = f.get('format_note', '')
                
                print_log(f"Format {format_id}: vcodec={vcodec}, acodec={acodec}, ext={ext}, note={format_note}")
                
                if vcodec == 'none' and acodec != 'none':
                    # Audio-only format
                    abr = f.get('abr', 0)
                    label = f" {abr}kbps, {acodec}, {ext}, ~{size_mb:.2f} MB"
                    audioonly_streams.append((label, f, abr))
                    print_log(f"  -> Categorized as audio-only")
                elif vcodec != 'none' and acodec != 'none':
                    # Video with audio
                    height = f.get('height', 0)
                    fps = f.get('fps', 0)
                    vbr = f.get('vbr', 0) or f.get('tbr', 0)
                    vcodec_display = vcodec.replace('avc1', 'h264')
                    label = f" {height}p{fps} ({vbr:.1f}kbps), {vcodec_display}+{acodec}, {ext}, ~{size_mb:.2f} MB"
                    combined_streams.append((label, f, (height, fps)))
                    print_log(f"  -> Categorized as video+audio")
                elif vcodec != 'none':
                    # Video-only format
                    height = f.get('height', 0)
                    fps = f.get('fps', 0)
                    vbr = f.get('vbr', 0) or f.get('tbr', 0)
                    vcodec_display = vcodec.replace('avc1', 'h264')
                    label = f" {height}p{fps} ({vbr:.1f}kbps), {vcodec_display}, {ext}, ~{size_mb:.2f} MB"
                    videoonly_streams.append((label, f, (height, fps)))
                    print_log(f"  -> Categorized as video-only")
            
            # Sort streams by quality
            def safe_sort_key_video(x):
                height = x[2][0] or 0
                fps = x[2][1] or 0
                tbr = x[1].get('tbr', 0) or x[1].get('tbr', 0)
                return (height, fps, tbr)
                
            def safe_sort_key_audio(x):
                abr = x[2] or 0
                tbr = x[1].get('tbr', 0) or 0
                return (abr, tbr)
            
            combined_streams.sort(key=safe_sort_key_video, reverse=True)
            videoonly_streams.sort(key=safe_sort_key_video, reverse=True)
            audioonly_streams.sort(key=safe_sort_key_audio, reverse=True)
            
            # Clear existing dropdowns and reset to None
            youtube_combined_dropdown['menu'].delete(0, 'end')
            youtube_videoonly_dropdown['menu'].delete(0, 'end')
            youtube_audioonly_dropdown['menu'].delete(0, 'end')
            youtube_streams.clear()
            
            selected_combined_var.set("None")
            selected_videoonly_var.set("None")
            selected_audioonly_var.set("None")
            
            # Add None option to each dropdown
            youtube_combined_dropdown['menu'].add_command(
                label="None",
                command=tk._setit(selected_combined_var, "None")
            )
            youtube_videoonly_dropdown['menu'].add_command(
                label="None",
                command=tk._setit(selected_videoonly_var, "None")
            )
            youtube_audioonly_dropdown['menu'].add_command(
                label="None",
                command=tk._setit(selected_audioonly_var, "None")
            )
            
            # Populate combined streams dropdown
            if combined_streams:
                for label, fmt, _ in combined_streams:
                    youtube_streams[label] = fmt
                    youtube_combined_dropdown['menu'].add_command(
                        label=label,
                        command=lambda l=label: (
                            selected_combined_var.set(l),
                            on_format_selected(selected_combined_var, [selected_videoonly_var, selected_audioonly_var])
                        )
                    )
            
            # Populate video-only streams dropdown
            if videoonly_streams:
                for label, fmt, _ in videoonly_streams:
                    youtube_streams[label] = fmt
                    youtube_videoonly_dropdown['menu'].add_command(
                        label=label,
                        command=lambda l=label: (
                            selected_videoonly_var.set(l),
                            on_format_selected(selected_videoonly_var, [selected_combined_var, selected_audioonly_var])
                        )
                    )
            
            # Populate audio-only streams dropdown
            if audioonly_streams:
                for label, fmt, _ in audioonly_streams:
                    youtube_streams[label] = fmt
                    youtube_audioonly_dropdown['menu'].add_command(
                        label=label,
                        command=lambda l=label: (
                            selected_audioonly_var.set(l),
                            on_format_selected(selected_audioonly_var, [selected_combined_var, selected_videoonly_var])
                        )
                    )

            print_log(f"Loaded {len(combined_streams)} combined, {len(videoonly_streams)} video-only, and {len(audioonly_streams)} audio-only formats.")
            
    except Exception as e:
        print_log(f"Error: {str(e)}")
        print_log(f"Error type: {type(e)}")
        messagebox.showerror("Error", f"Could not initialize YouTube: {e}")
        return

def combine_files_ffmpeg(video_path: Path, audio_path: Path, output_path: Path):
    """
    Combine video-only and audio-only into one final file using ffmpeg.
    Both streams are copied without transcoding (if possible).
    """
    print_log(f"Combining with FFmpeg:\n  Video: {video_path}\n  Audio: {audio_path}\n  => Output: {output_path}")
    try:
        # Shell command to combine without re-encoding
        # Make sure ffmpeg is available in PATH
        cmd = [
            "ffmpeg",
            "-y",  # overwrite
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "copy",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print_log("FFmpeg merge completed successfully.")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode().strip()
        print_log(f"FFmpeg merge error: {error_message}")
        messagebox.showerror("Error", f"FFmpeg merge failed: {error_message}")

def download_youtube_once(url: str, destination: Path, download_id: str):
    video_path = os.path.join(destination, 'video.mp4')
    audio_path = os.path.join(destination, 'audio.mp3')
    output_path = os.path.join(destination, 'final_video.mp4')

    if combine_av_var.get():
        video_label = selected_videoonly_var.get()
        audio_label = selected_audioonly_var.get()

        if video_label == "None" or audio_label == "None":
            print_log("Error: You must select both a video-only and an audio-only format.")
            messagebox.showerror("Error", "Please select both a video-only and an audio-only format.")
            return

        video_fmt = youtube_streams.get(video_label)
        audio_fmt = youtube_streams.get(audio_label)

        if not video_fmt or not audio_fmt:
            print_log("Error: Could not find selected formats in dictionary.")
            messagebox.showerror("Error", "Selected formats not found.")
            return

        def format_speed(bytes_per_second):
            if bytes_per_second < 1024:
                return f"{bytes_per_second:.1f} B/s"
            elif bytes_per_second < 1024 * 1024:
                return f"{bytes_per_second/1024:.1f} KB/s"
            else:
                return f"{bytes_per_second/(1024*1024):.1f} MB/s"

        # Separate progress hooks for video and audio
        def progress_hook_video(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed', 0)

                    if total and speed:
                        percentage = (downloaded / total) * 100
                        speed_str = format_speed(speed)
                        progress_text = f"{percentage:.1f}% @ {speed_str}"

                        # Update video progress bar using thread-safe method
                        root.after(0, lambda: update_progress(download_id, int(percentage), speed=speed_str))
                except Exception as e:
                    print_log(f"Progress error (video): {e}")
            elif d['status'] == 'finished':
                root.after(0, lambda: update_progress(download_id, 100, text="Video Done - 100%"))

        def progress_hook_audio(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed', 0)

                    if total and speed:
                        percentage = (downloaded / total) * 100
                        speed_str = format_speed(speed)
                        progress_text = f"{percentage:.1f}% @ {speed_str}"

                        # Update audio progress bar using thread-safe method
                        root.after(0, lambda: update_progress(download_id, int(percentage), speed=speed_str))
                except Exception as e:
                    print_log(f"Progress error (audio): {e}")
            elif d['status'] == 'finished':
                root.after(0, lambda: update_progress(download_id, 100, text="Audio Done - 100%"))
                # Hide the audio progress bar after completion
                root.after(1000, lambda: remove_progress_bar(download_id))

        def download_video():
            print_log('Downloading video...')
            root.after(0, lambda: update_progress(download_id, 0))
            ydl_opts_video = {
                'format': video_fmt['format_id'],
                'outtmpl': str(video_path),
                'progress_hooks': [progress_hook_video],
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
                ydl.download([url])
            print_log('Video downloaded.')

        def download_audio():
            print_log('Downloading audio...')
            root.after(0, lambda: update_progress(download_id, 0))
            ydl_opts_audio = {
                'format': audio_fmt['format_id'],
                'outtmpl': str(audio_path),
                'progress_hooks': [progress_hook_audio],
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                ydl.download([url])
            print_log('Audio downloaded.')

        video_thread = threading.Thread(target=download_video)
        audio_thread = threading.Thread(target=download_audio)

        video_thread.start()
        audio_thread.start()

        video_thread.join()
        audio_thread.join()

        time.sleep(5)  # Wait for 5 seconds before muxing

        # Check if both files exist before muxing
        if os.path.exists(video_path) and os.path.exists(audio_path):
            combine_files_ffmpeg(video_path, audio_path, output_path)
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            print_log('Muxing complete. Original files deleted.')
        else:
            print_log("Error: One or both files are missing for muxing.")
            messagebox.showerror("Error", "Failed to combine video and audio.")
    else:
        # Existing single download logic
        chosen_label = selected_combined_var.get() if selected_combined_var.get() != "None" else \
                       selected_videoonly_var.get() if selected_videoonly_var.get() != "None" else \
                       selected_audioonly_var.get()

        chosen_format = youtube_streams.get(chosen_label) if chosen_label else None

        if not chosen_format:
            print_log("No format selected.")
            messagebox.showerror("Error", "Please select a format to download.")
            return

        ydl_opts = {
            'format': chosen_format['format_id'],
            'outtmpl': str(destination / '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True
        }

        print_log(f"Initializing single-format download for: {url}")
        current_file_var.set(f"Downloading (YouTube): {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                print_log(f"Title: {info.get('title', 'Unknown')}")
                print_log(f"Duration: {info.get('duration', 'Unknown')} seconds")

                # Actually download
                ydl.download([url])

                print_log("Download completed successfully!")
                update_progress(download_id, 100)
                current_file_var.set("")

            except Exception as e:
                print_log(f"Download failed: {str(e)}")
                messagebox.showerror("Error", f"Download failed: {e}")
                current_file_var.set("")
                return

class SegmentedProgressBar(tk.Canvas):
    def __init__(self, master, **kwargs):
        self.height = kwargs.pop('height', progress_thickness)
        self.segments = []  # List of (start, end, color) tuples
        self.bright_colors = ['#FF0000', '#00FF00', '#0000FF', '#FFD700', '#FF00FF', '#00FFFF']  # Red, Green, Blue, Gold, Magenta, Cyan
        self.default_color = self.bright_colors[0]  # Default to first color
        super().__init__(master, height=self.height, bg='white', highlightthickness=0, **kwargs)
        self.bind('<Configure>', self._on_resize)
        
    def _on_resize(self, event):
        """Handle resize events"""
        self.update_layout()
        
    def update_layout(self):
        """Update the layout of all elements"""
        self.update_segments()
    
    def set_segments(self, segments):
        """Set the segments of the progress bar
        segments: list of (thread_index, start_percent, end_percent) tuples
        """
        # Assign colors to segments based on thread index
        colored_segments = []
        for thread_idx, start, end in segments:
            color = self.bright_colors[thread_idx % len(self.bright_colors)]
            colored_segments.append((start, end, color))
        self.segments = colored_segments
        self.update_segments()
    
    def update_segments(self):
        """Update the visual representation of segments"""
        self.delete('all')  # Clear all existing shapes
        
        w = self.winfo_width()
        h = self.height
        
        # Draw segments
        for start_pct, end_pct, color in self.segments:
            x1 = w * (start_pct / 100)
            x2 = w * (end_pct / 100)
            self.create_rectangle(x1, 0, x2, h, fill=color, width=0)

def download_regular_once(
    url: str,
    destination: Path,
    base_name: str = "",
    file_index=1,
    total_files=1,
    download_id=None
):
    if not SmartDL:
        print_log("pySmartDL is not installed or failed to import.")
        return False

    if download_id is None:
        download_id = get_next_bar_id()

    n_threads = threads_var.get()
    if n_threads < 1:
        n_threads = 1

    max_tries = attempts_var.get()
    if max_tries < 1:
        max_tries = 1

    # Get the base name from the input field
    if base_name:
        user_base, user_ext = os.path.splitext(base_name)
        if user_ext:
            final_ext = user_ext
        else:
            guessed_ext = guess_extension_from_url(url)
            final_ext = guessed_ext

        # Append index only if multiple links are provided
        if total_files > 1:
            final_filename = f"{user_base}{file_index}{final_ext}"
        else:
            final_filename = f"{user_base}{final_ext}"  # No index for single download
    else:
        # If no base name is provided, use the original filename from the URL
        final_filename = os.path.basename(url)

    final_path = destination / final_filename
    current_file_var.set(f"Currently downloading: {final_filename}")
    short_name = final_filename
    print_log(f"Downloading: {short_name}")

    tries = 0
    WAIT_BETWEEN_TRIES = 5
    MAX_COMBINE_RETRIES = 5
    COMBINE_RETRY_DELAY = 2
    MAX_CLEANUP_RETRIES = 5
    CLEANUP_BASE_DELAY = 1
    
    while tries < max_tries:
        tries += 1
        print_log(f"Attempt {tries}/{max_tries} for {short_name}...")
        print_log("-"*10)

        downloader = SmartDL(url, str(final_path), threads=n_threads, timeout=300)
        
        try:
            downloader.start(blocking=False)

            while not downloader.isFinished():
                progress = downloader.get_progress() * 100
                speed = downloader.get_speed(human=True)
                
                segments = []
                if hasattr(downloader, 'threads'):
                    total_size = downloader.filesize or 1
                    chunk_size = total_size / n_threads
                    
                    for i in range(n_threads):
                        thread = downloader.threads[i]
                        if thread and hasattr(thread, 'downloaded'):
                            start_pct = (i * chunk_size / total_size) * 100
                            current_progress = thread.downloaded / total_size * 100
                            if current_progress > 0:
                                segments.append((i, start_pct, start_pct + current_progress))
                
                if not segments:
                    segments = [(0, 0, progress)]
                
                root.after(0, lambda p=progress, s=speed, fn=short_name, seg=segments: 
                          update_progress(download_id, p, speed=s, text=fn, segments=seg))
                time.sleep(0.1)

            if downloader.isSuccessful():
                # Try to combine files with retries and exponential backoff
                combine_tries = 0
                while combine_tries < MAX_COMBINE_RETRIES:
                    try:
                        time.sleep(COMBINE_RETRY_DELAY * (2 ** combine_tries))
                        
                        # Attempt cleanup with exponential backoff
                        cleanup_tries = 0
                        cleanup_success = False
                        
                        while cleanup_tries < MAX_CLEANUP_RETRIES and not cleanup_success:
                            try:
                                # Get list of temporary files
                                temp_files = [f for f in os.listdir(destination) 
                                           if f.startswith(final_filename) and f.endswith('.000')]
                                
                                # Try to remove each temporary file
                                for temp_file in temp_files:
                                    temp_path = destination / temp_file
                                    try:
                                        os.remove(temp_path)
                                        print_log(f"Successfully removed temporary file: {temp_file}")
                                    except PermissionError:
                                        print_log(f"Permission denied for {temp_file}, retrying...")
                                        raise
                                    except Exception as e:
                                        print_log(f"Error removing {temp_file}: {str(e)}")
                                        raise
                                
                                cleanup_success = True
                                
                            except Exception as e:
                                cleanup_tries += 1
                                if cleanup_tries < MAX_CLEANUP_RETRIES:
                                    delay = CLEANUP_BASE_DELAY * (2 ** cleanup_tries)
                                    print_log(f"Cleanup attempt {cleanup_tries} failed, waiting {delay}s...")
                                    time.sleep(delay)
                                else:
                                    print_log("Max cleanup retries reached, continuing anyway...")
                                    break
                        
                        if cleanup_success or cleanup_tries >= MAX_CLEANUP_RETRIES:
                            print_log(f"Download of {short_name} completed successfully!")
                            update_progress(download_id, 100)
                            current_file_var.set("")
                            return True
                            
                    except Exception as e:
                        combine_tries += 1
                        if combine_tries < MAX_COMBINE_RETRIES:
                            print_log(f"Combine attempt {combine_tries} failed: {str(e)}")
                            continue
                        else:
                            print_log("Max combine retries reached.")
                            raise
                
                print_log(f"Failed to combine files after {MAX_COMBINE_RETRIES} attempts.")
                return False
                
            else:
                error = downloader.get_errors()[0] if downloader.get_errors() else "Unknown error"
                print_log(f"Download failed on attempt {tries}: {error}")
                if tries < max_tries:
                    print_log(f"Waiting {WAIT_BETWEEN_TRIES} seconds before next attempt...")
                    time.sleep(WAIT_BETWEEN_TRIES)
                    continue
                else:
                    print_log("Max retries reached. Download failed.")
                    messagebox.showerror("Error", f"Download failed after {max_tries} attempts: {error}")
                    current_file_var.set("")
                    return False
                    
        except Exception as e:
            print_log(f"Error during download: {str(e)}")
            if tries < max_tries:
                print_log(f"Waiting {WAIT_BETWEEN_TRIES} seconds before next attempt...")
                time.sleep(WAIT_BETWEEN_TRIES)
                continue
            else:
                print_log("Max retries reached. Download failed.")
                messagebox.showerror("Error", f"Download failed after {max_tries} attempts: {str(e)}")
                current_file_var.set("")
                return False

    return False

def guess_extension_from_url(url: str):
    ext = Path(url).suffix
    if ext and len(ext) <= 5:
        return ext
    return ".bin"

def process_links_sequential(links: list[str]):
    def do_batch():
        dest = Path(dest_folder_var.get())
        base_name = filename_var.get()
        total_count = len(links)
        num_success = 0

        for i, link in enumerate(links, start=1):
            download_id = get_next_bar_id()
            root.after(0, lambda: update_progress(download_id, 0))

            if "youtube.com" in link or "youtu.be" in link:
                print_log(f"[{i}/{total_count}] YouTube link: {link}")
                if download_youtube_once(link, dest, download_id):
                    num_success += 1
            else:
                print_log(f"[{i}/{total_count}] Regular link: {link}")
                if download_regular_once(
                    link, 
                    dest,
                    base_name,
                    file_index=i,
                    total_files=total_count,
                    download_id=download_id
                ):
                    num_success += 1

        open_folder(dest)
        print_log(f"{num_success} of {total_count} downloads finished successfully.")
        print_log("-"*10)

    threading.Thread(target=do_batch, daemon=True).start()

def get_links_list() -> list[str]:
    raw_text = links_text.get("1.0", tk.END)
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    return lines

def check_link_types(*args):
    lines = get_links_list()
    if not lines:
        if youtube_frame.winfo_ismapped():
            youtube_frame.pack_forget()
        if regular_frame.winfo_ismapped():
            regular_frame.pack_forget()
        frame_mid.pack_forget()  # Hide the middle frame completely
        root.update_idletasks()  # Force geometry update
        root.geometry('')  # Reset window size to fit content
        return

    has_youtube = any(("youtube.com" in ln or "youtu.be" in ln) for ln in lines)
    has_regular = any(not ("youtube.com" in ln or "youtu.be" in ln) for ln in lines)

    if not frame_mid.winfo_ismapped():
        frame_mid.pack(fill="x", after=frame_filename)  # Show middle frame if needed

    if has_youtube and not youtube_frame.winfo_ismapped():
        youtube_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    elif not has_youtube and youtube_frame.winfo_ismapped():
        youtube_frame.pack_forget()

    if has_regular and not regular_frame.winfo_ismapped():
        regular_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)
    elif not has_regular and regular_frame.winfo_ismapped():
        regular_frame.pack_forget()

    if not (has_youtube or has_regular):
        frame_mid.pack_forget()  # Hide middle frame if no options needed

    root.update_idletasks()  # Force geometry update
    root.geometry('')  # Reset window size to fit content

def toggle_format_dropdowns():
    """
    Show/hide dropdowns based on the state of combine_av_var.
    Uses grid_remove() and grid() instead of pack to maintain consistency.
    """
    if combine_av_var.get():
        # Hide Combined dropdown
        youtube_combined_dropdown.grid_remove()
        # Show Video-Only and Audio-Only dropdowns
        youtube_videoonly_label.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        youtube_videoonly_dropdown.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        youtube_audioonly_label.grid(row=3, column=0, sticky="e", padx=5, pady=5)
        youtube_audioonly_dropdown.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    else:
        # Show Combined dropdown
        youtube_combined_dropdown.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        # Hide Video-Only and Audio-Only dropdowns
        youtube_videoonly_dropdown.grid_remove()
        youtube_audioonly_dropdown.grid_remove()
        # Hide corresponding labels
        youtube_videoonly_label.grid_remove()
        youtube_audioonly_label.grid_remove()

def single_download():
    #clear_log()
    lines = get_links_list()
    if not lines:
        print_log("No links found.")
        return

    if len(lines) == 1:
        process_links_sequential(lines)
    else:
        print_log(f"Batch Download mode. Found {len(lines)} links.")
        process_links_sequential(lines)

# Initialize Tkinter root
root = tk.Tk()
root.title(f"Just Download It! EXPERIMENTAL v{version}")
root.geometry("600x800")

# Style for the label overlay
style = ttk.Style()

# Use a theme that allows styling
style.theme_use('clam')

# Define Tkinter variables
threads_var      = tk.IntVar(value=4)
attempts_var     = tk.IntVar(value=3)
filename_var     = tk.StringVar()
selected_combined_var = tk.StringVar(value="None")
selected_videoonly_var = tk.StringVar(value="None")
selected_audioonly_var = tk.StringVar(value="None")
current_file_var = tk.StringVar(value="")
combine_av_var   = tk.BooleanVar(value=False)  # For separate audio+video downloads
progress_thickness = 5  # Global setting for progress bar thickness

# Configure the custom style for a slim progress bar
style.configure("custom.Horizontal.TProgressbar",
                troughcolor='white',       # Background color of the trough
                background='#4a90e2',      # Progress bar color
                thickness=progress_thickness)  # Use global thickness setting

# Modify the layout to remove padding and enforce slim appearance
style.layout("custom.Horizontal.TProgressbar", 
            [('Horizontal.Progressbar.trough',
              {'sticky': 'nswe', 'children': [('Horizontal.Progressbar.pbar',
                                              {'side': 'left', 'sticky': 'ns'})]})])

# Configure the trough element to be slim
style.configure("Horizontal.TProgressbar", thickness=progress_thickness)  # Use global thickness setting

# Style for the progress bar label
style.configure("PbarOverlay.TLabel", 
                background='white',
                font=('Arial', 8))  # Smaller font for the overlay text

# Create frames
frame_top       = ttk.Frame(root, padding=10)
frame_filename  = ttk.Frame(root, padding=10)
frame_mid       = ttk.Frame(root, padding=10)
frame_bottom    = ttk.Frame(root, padding=10)

frame_top.pack(fill="x")
frame_filename.pack(fill="x")
# Don't pack frame_mid initially - it will be packed when needed
frame_bottom.pack(fill="both", expand=True)

# Top Frame: Download Links
ttk.Label(frame_top, text="Download Links (one per line):").pack(anchor="w")
links_text = tk.Text(frame_top, width=70, height=5)
links_text.pack(fill="x", pady=5)
links_text.bind("<KeyRelease>", check_link_types)

# Filename and Destination Folder Frame
ttk.Label(frame_filename, text="Filename (optional extension):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
filename_entry = ttk.Entry(frame_filename, textvariable=filename_var, width=50)
filename_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

ttk.Label(frame_filename, text="Destination Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
dest_folder_var = tk.StringVar(value=str(Path.cwd()))
dest_entry = ttk.Entry(frame_filename, textvariable=dest_folder_var, width=50)
dest_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

def browse_folder():
    folder = filedialog.askdirectory(title="Select Destination Folder")
    if folder:
        dest_folder_var.set(folder)

ttk.Button(frame_filename, text="Browse...", command=browse_folder).grid(row=1, column=2, padx=5, pady=5, sticky="w")

# Middle Frame: YouTube and Regular Download Options
youtube_frame = ttk.LabelFrame(frame_mid, text="YouTube Options", padding=10)
youtube_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

load_streams_btn = ttk.Button(youtube_frame, text="Load Streams", command=load_youtube_streams)
load_streams_btn.grid(row=0, column=0, columnspan=2, padx=5, pady=5)

# NEW: Checkbutton to toggle separate audio/video downloads (Placed above dropdowns)
combine_av_chk = ttk.Checkbutton(
    youtube_frame, 
    text="Separate AV",
    variable=combine_av_var,
    command=toggle_format_dropdowns  # Call this function when checkbox state changes
)
combine_av_chk.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

# Combined (Video+Audio) dropdown
youtube_combined_label = ttk.Label(youtube_frame, text="Video + Audio:")
youtube_combined_label.grid(row=2, column=0, sticky="e", padx=5, pady=5)
youtube_combined_dropdown = ttk.OptionMenu(youtube_frame, selected_combined_var, "None")
youtube_combined_dropdown.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

# Video-only dropdown
youtube_videoonly_label = ttk.Label(youtube_frame, text="Video Only:")
youtube_videoonly_label.grid(row=3, column=0, sticky="e", padx=5, pady=5)
youtube_videoonly_dropdown = ttk.OptionMenu(youtube_frame, selected_videoonly_var, "None")
youtube_videoonly_dropdown.grid(row=3, column=1, sticky="ew", padx=5, pady=5)

# Audio-only dropdown
youtube_audioonly_label = ttk.Label(youtube_frame, text="Audio Only:")
youtube_audioonly_label.grid(row=4, column=0, sticky="e", padx=5, pady=5)
youtube_audioonly_dropdown = ttk.OptionMenu(youtube_frame, selected_audioonly_var, "None")
youtube_audioonly_dropdown.grid(row=4, column=1, sticky="ew", padx=5, pady=5)

# Configure column weight to make dropdowns expand
youtube_frame.columnconfigure(1, weight=1)

# Regular Download Frame
regular_frame = ttk.LabelFrame(frame_mid, text="Regular Download (pySmartDL)", padding=10)
regular_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

ttk.Label(regular_frame, text="Threads:").grid(row=0, column=0, sticky="e", padx=5, pady=5)

def update_threads_label(value):
    threads_value_label.config(text=str(int(float(value))))

threads_slider = ttk.Scale(regular_frame, from_=1, to_=64, orient="horizontal",
                           variable=threads_var, command=update_threads_label)
threads_slider.grid(row=0, column=1, sticky="we", padx=5, pady=5)
threads_value_label = ttk.Label(regular_frame, text=str(threads_var.get()))
threads_value_label.grid(row=0, column=2, padx=5, pady=5)

ttk.Label(regular_frame, text="Attempts:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
attempts_entry = ttk.Entry(regular_frame, textvariable=attempts_var, width=5)
attempts_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

# Bottom Frame: Download Button, Current File, Progress Bar, and Log
download_btn = ttk.Button(frame_bottom, text="Download", command=single_download)
download_btn.pack(pady=5)

# Frame to contain all progress bars
progress_bars_frame = ttk.Frame(frame_bottom)
progress_bars_frame.pack(fill="x", padx=5, pady=5)

# Dictionary to store progress bars and their labels
progress_bars = {}
next_bar_id = 0  # Counter for generating unique bar IDs

def get_next_bar_id():
    """Get the next available bar ID"""
    global next_bar_id
    next_bar_id += 1
    return f"bar_{next_bar_id}"

def create_progress_bar(download_id=None):
    """Create a new progress bar container and return its components"""
    if download_id is None:
        download_id = get_next_bar_id()
        
    def _create():
        # Create a container frame
        container = ttk.Frame(progress_bars_frame)
        container.pack(fill="x", pady=1)
        
        # Inner frame for the actual progress bar and label
        inner_frame = ttk.Frame(container)
        inner_frame.pack(fill="x", padx=1, pady=1)
        
        # Create label on the left
        label = ttk.Label(inner_frame, text="", anchor="w")
        label.pack(side="left", padx=(5, 10))  # Add padding between label and progress bar
        
        progress_var = tk.IntVar(value=0)
        
        # Create custom segmented progress bar
        progress_bar = SegmentedProgressBar(inner_frame)
        progress_bar.pack(side="left", fill="x", expand=True)  # Fill remaining space
        
        progress_bars[download_id] = (container, progress_var, progress_bar, label)
    
    root.after(0, _create)
    return download_id

def remove_progress_bar(download_id):
    """Remove a progress bar and its components"""
    if download_id in progress_bars:
        container, _, _, _ = progress_bars[download_id]
        container.destroy()
        del progress_bars[download_id]
        reposition_bars()

def reposition_bars():
    """Reposition all progress bars to eliminate gaps"""
    # Get all visible bars
    visible_bars = [(id, bar[0]) for id, bar in progress_bars.items()]
    
    # Sort by current position
    visible_bars.sort(key=lambda x: x[1].winfo_y())
    
    # Reposition each bar
    for i, (bar_id, container) in enumerate(visible_bars):
        target_y = i * (container.winfo_height() + 2)  # 2 pixels spacing
        if container.winfo_y() != target_y:
            container.pack_configure(pady=1)

def update_progress(download_id, progress, speed="", text="", segments=None):
    """Update progress and text for a specific progress bar"""
    def _update():
        if download_id not in progress_bars:
            create_progress_bar(download_id)
            # Wait a brief moment for create_progress_bar to complete
            root.after(10, lambda: _update())
            return
        
        container, progress_var, progress_bar, label = progress_bars[download_id]
        progress_var.set(progress)
        
        # Update segments if provided
        if segments:
            progress_bar.set_segments(segments)
        else:
            # Default single segment
            progress_bar.set_segments([(0, 0, progress)])
        
        # Update label text with filename and progress
        if text:
            if speed:
                label.config(text=f"{text} - {speed} - {progress:.1f}%")
            else:
                label.config(text=text)
        
        if progress >= 100:
            # Remove progress bar after a short delay
            root.after(1000, lambda: remove_progress_bar(download_id))
    
    root.after(0, _update)

# Log box below progress bars
log_box = tk.Text(frame_bottom, height=10, state=tk.DISABLED)
log_box.pack(fill="both", expand=True, padx=5, pady=5)

# Initialize dropdown visibility based on the initial state of combine_av_var
toggle_format_dropdowns()

check_link_types()

root.mainloop()
