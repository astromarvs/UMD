import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlparse
import yt_dlp
import re
import subprocess
import platform

from downloader import download_facebook, download_instagram, download_tiktok, download_youtube

def main_window():
    def is_valid_url(url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url.strip())
        return bool(parsed.scheme and parsed.netloc)

    def strip_ansi(text):
        return re.sub(r'\x1b\[[0-9;]*[mK]', '', text)

    def log_callback(msg):
        clean_msg = strip_ansi(msg)
        progress_text.configure(state='normal')
        progress_text.insert(tk.END, clean_msg + '\n')
        progress_text.see(tk.END)
        progress_text.configure(state='disabled')

    def progress_hook(status):
        if status['status'] == 'finished':
            full_path = status.get('filename', '')
            clean_path = strip_ansi(full_path)
            base_name = os.path.basename(clean_path)
            progress_label.config(text=f"Download completed: {base_name}")
            open_location_button.config(state='normal')
            enable_download_fields()  # Re-enable fields
            # Clear input fields
            url_entry.delete(0, tk.END)
            output_path_var.set('')
            format_var.set('mp4')
            subtitle_var.set('none')
            subtitle_check_var.set(False)
            # Show completion message
            messagebox.showinfo("Download Completed", f"{base_name} has been downloaded successfully!")
        elif status['status'] == 'downloading':
            percent = strip_ansi(status.get('_percent_str', '').strip())
            speed = strip_ansi(status.get('_speed_str', '').strip())
            eta = strip_ansi(status.get('_eta_str', '').strip())
            progress_label.config(text=f"Downloading... {percent} at {speed}, ETA: {eta}")


    def select_output_file():
        fmt = format_var.get()
        if not fmt:
            messagebox.showwarning("Warning", "Select a format first")
            return
        def_ext = ".mp3" if fmt == "mp3" else ".mp4"
        path = filedialog.asksaveasfilename(
            defaultextension=def_ext,
            filetypes=[(f"{fmt.upper()} files", f"*{def_ext}")]
        )
        if path:
            output_path_var.set(path)

    def handle_download():
        url = url_entry.get().strip()
        if not is_valid_url(url):
            messagebox.showerror("Error", "Please enter a valid URL")
            return
        output_full_path = output_path_var.get().strip()
        if not output_full_path:
            messagebox.showerror("Error", "Please select an output file")
            return
        output_folder = os.path.dirname(output_full_path)
        raw_name, raw_ext = os.path.splitext(os.path.basename(output_full_path))
        fmt = format_var.get()

        def run_download():
            try:
                if "youtube.com" in url or "youtu.be" in url:
                    download_youtube(
                        url, output_folder, raw_name, fmt,
                        progress_hook=progress_hook,
                        log_callback=log_callback,
                        subtitle_lang=subtitle_var.get(),
                        download_subtitles=subtitle_check_var.get()
                    )
                elif "tiktok.com" in url:
                    download_tiktok(url, output_folder, raw_name, fmt, progress_hook=progress_hook, log_callback=log_callback)
                elif "instagram.com" in url:
                    download_instagram(url, output_folder, raw_name, fmt, progress_hook=progress_hook, log_callback=log_callback)
                elif "facebook.com" in url:
                    download_facebook(url, output_folder, raw_name, fmt, progress_hook=progress_hook, log_callback=log_callback)
                else:
                    log_callback("Unsupported URL — only YouTube, TikTok, Instagram, Facebook")
            except Exception as e:
                messagebox.showerror("Download error", str(e))

        threading.Thread(target=run_download, daemon=True).start()

    def disable_download_fields():
        output_entry.config(state='disabled')
        browse_button.config(state='disabled')
        format_dropdown.config(state='disabled')
        subtitle_dropdown.config(state='disabled')
        subtitle_check.config(state='disabled')
        download_button.config(state='disabled')
        open_location_button.config(state='disabled')

    def enable_download_fields():
        output_entry.config(state='normal')
        browse_button.config(state='normal')
        format_dropdown.config(state='readonly')
        subtitle_dropdown.config(state='readonly')
        subtitle_check.config(state='normal')
        download_button.config(state='normal')

    def hide_platform_specific_fields():
        subtitle_label.grid_remove()
        subtitle_dropdown.grid_remove()
        subtitle_check.grid_remove()

    def check_url():
        url = url_entry.get().strip()
        if not is_valid_url(url):
            messagebox.showerror("Error", "Please enter a valid URL first.")
            return

        disable_download_fields()
        hide_platform_specific_fields()
        progress_label.config(text="Checking URL...")
        root.update()

        def check_url_thread():
            try:
                if "youtube.com" in url or "youtu.be" in url:
                    ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'playlistend': 1}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        root.after(0, lambda: handle_youtube_url(url, info))
                elif "tiktok.com" in url:
                    root.after(0, handle_tiktok_url)
                elif "instagram.com" in url or "facebook.com" in url:
                    root.after(0, handle_instagram_facebook_url)
                else:
                    root.after(0, lambda: messagebox.showinfo("Info", "Unsupported domain"))
            except Exception as e:
                root.after(0, lambda: progress_label.config(text=f"Error checking URL: {str(e)}"))

        threading.Thread(target=check_url_thread, daemon=True).start()

    def handle_youtube_url(url, info):
        format_dropdown.config(values=["mp4", "mp3"])
        format_var.set("mp4")

        if info and info.get('_type') == 'playlist':
            log_callback("Playlist detected - will download only the first video")
            messagebox.showinfo("Playlist Detected", "Only the first video will be downloaded.")

        if info and info.get('_type') != 'playlist':
            try:
                ydl_opts = {'quiet': True, 'skip_download': True, 'writesubtitles': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    vid_info = ydl.extract_info(url, download=False)
                    subs = list(vid_info.get('subtitles', {}).keys())
                    if subs:
                        subtitle_label.grid()
                        subtitle_dropdown.config(values=["none"] + subs)
                        subtitle_var.set("none")
                        subtitle_dropdown.grid()
                        subtitle_check_var.set(False)
                        subtitle_check.grid()
                        log_callback(f"Subtitles available: {', '.join(subs)}")
                    else:
                        log_callback("No subtitles available.")
            except Exception as e:
                log_callback(f"Failed to fetch subtitles: {e}")

        enable_download_fields()
        progress_label.config(text="YouTube URL ready")

    def handle_tiktok_url():
        format_dropdown.config(values=["mp4"])
        format_var.set("mp4")
        enable_download_fields()
        log_callback("TikTok URL detected")
        progress_label.config(text="TikTok URL ready")

    def handle_instagram_facebook_url():
        format_dropdown.config(values=["mp4", "jpg", "jpeg"])
        format_var.set("mp4")
        enable_download_fields()
        log_callback("Instagram/Facebook URL detected")
        progress_label.config(text="Instagram/Facebook URL ready")

    def open_file_location():
        full_path = output_path_var.get().strip()
        if not full_path or not os.path.exists(full_path):
            messagebox.showerror("Error", "Downloaded file not found or path is invalid.")
            return
        folder = os.path.dirname(full_path)
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder: {e}")

    # --- GUI Layout ---
    root = tk.Tk()
    root.title("Universal Media Downloader")
    root.geometry("700x600")

    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # URL
    ttk.Label(main_frame, text="Media URL:").grid(row=0, column=0, sticky="w", pady=5)
    url_entry = ttk.Entry(main_frame, width=60)
    url_entry.grid(row=0, column=1, sticky="we", pady=5, padx=5)
    check_button = ttk.Button(main_frame, text="Check URL", command=check_url)
    check_button.grid(row=0, column=2, sticky="w", padx=5)

    # Format + Output
    ttk.Label(main_frame, text="Format / Output file:").grid(row=1, column=0, sticky="w", pady=5)
    format_var = tk.StringVar(value="")
    format_dropdown = ttk.Combobox(main_frame, textvariable=format_var, state='disabled', width=10)
    format_dropdown.grid(row=1, column=1, sticky="w", padx=(0,5))
    output_path_var = tk.StringVar()
    output_entry = ttk.Entry(main_frame, textvariable=output_path_var, width=40, state='disabled')
    output_entry.grid(row=1, column=1, sticky="we", padx=(100,5))
    browse_button = ttk.Button(main_frame, text="Select...", command=select_output_file, state='disabled')
    browse_button.grid(row=1, column=2, sticky="w", padx=5)

    # Subtitles
    subtitle_label = ttk.Label(main_frame, text="Subtitles:")
    subtitle_label.grid(row=2, column=0, sticky="w", pady=5)
    subtitle_label.grid_remove()
    subtitle_var = tk.StringVar(value="none")
    subtitle_dropdown = ttk.Combobox(main_frame, textvariable=subtitle_var, state='disabled')
    subtitle_dropdown.grid(row=2, column=1, sticky="we", pady=5, padx=5)
    subtitle_dropdown.grid_remove()
    subtitle_check_var = tk.BooleanVar(value=False)
    subtitle_check = ttk.Checkbutton(main_frame, text="Download subtitles", variable=subtitle_check_var, state='disabled')
    subtitle_check.grid(row=2, column=2, sticky="w", padx=5, pady=5)
    subtitle_check.grid_remove()

    # Download & Open location buttons
    download_button = ttk.Button(main_frame, text="Download", command=handle_download, state='disabled')
    download_button.grid(row=3, column=1, pady=10)
    open_location_button = ttk.Button(main_frame, text="Open File Location", command=open_file_location, state='disabled')
    open_location_button.grid(row=3, column=2, pady=10, padx=5, sticky="w")

    # Progress & Log
    progress_label = ttk.Label(main_frame, text="Enter a URL and click 'Check URL'")
    progress_label.grid(row=4, column=0, columnspan=3, sticky="we", pady=5)
    separator = ttk.Separator(main_frame, orient='horizontal')
    separator.grid(row=5, column=0, columnspan=3, sticky="we", pady=10)
    ttk.Label(main_frame, text="Download Log:").grid(row=6, column=0, sticky="w", pady=(0, 5))
    progress_text = tk.Text(main_frame, height=15, width=80, state='disabled')
    progress_text.grid(row=7, column=0, columnspan=3, pady=(0, 10), sticky="nsew")

    main_frame.columnconfigure(1, weight=1)
    main_frame.rowconfigure(7, weight=1)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    url_entry.focus_set()
    root.mainloop()
