import sys
import os
import time
import threading

# --windowed: sys.stdout / sys.stderr kaykouno None w kay7bssou tqdm/pooch
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageOps

# -----------------------------
# Application paths
# -----------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RESOURCE_DIR = BASE_DIR

MODELS_DIR = os.path.join(RESOURCE_DIR, "models")

# rembg kay9ra U2NET_HOME (machi REMBG_HOME) w kaytsenna l-fichiers .onnx
# mobachara dakhel had dossier: models/birefnet-general.onnx ...
os.environ["U2NET_HOME"] = MODELS_DIR

from rembg import remove, new_session

# =====================================
# APPLICATION SETTINGS
# =====================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Background Remover")

if getattr(sys, "frozen", False):
    icon_path = os.path.join(sys._MEIPASS, "assets", "icon.ico")
else:
    icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")

if os.path.exists(icon_path):
    app.iconbitmap(default=icon_path)

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 650
MIN_WIDTH = 850
MIN_HEIGHT = 620

app.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
app.minsize(MIN_WIDTH, MIN_HEIGHT)


def center_window():
    app.update_idletasks()
    screen_width = app.winfo_screenwidth()
    screen_height = app.winfo_screenheight()
    x = (screen_width - WINDOW_WIDTH) // 2
    y = (screen_height - WINDOW_HEIGHT) // 2
    app.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")


app.configure(fg_color="#111318")
center_window()

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except OSError:
    # fallback ila l-dossier ma ymkench kteba (ex: Program Files)
    OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "BackgroundRemover_output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================
# GLOBAL VARIABLES
# =====================================
selected_image = None
selected_megapixels = 0.0
original_preview_image = None
result_preview_image = None
result_image_path = None
result_image = None
ai_sessions = {}
is_processing = False

MODELS = {
    "birefnet-general": "birefnet-general",
    "birefnet-general-lite": "birefnet-general-lite",
    "u2netp": "u2netp",
}

processing_start_time = 0
estimated_seconds = None
average_seconds_per_mp = {}
timer_job = None

BLANK_IMAGE = ctk.CTkImage(
    light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
    dark_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
    size=(1, 1)
)

# =====================================
# COLORS
# =====================================
BG_COLOR = "#111318"
PANEL_COLOR = "#191C24"
PURPLE = "#7C3AED"
ACCENT = "#A78BFA"
TEXT_COLOR = "#FFFFFF"
GRAY = "#9CA3AF"
SUCCESS = "#22C55E"
ERROR = "#EF4444"

# =====================================
# HEADER
# =====================================
header = ctk.CTkFrame(app, fg_color="transparent")
header.pack(pady=(30, 10))

title = ctk.CTkLabel(
    header,
    text="Background Remover",
    font=("Arial", 30, "bold"),
    text_color=TEXT_COLOR
)
title.pack()

subtitle = ctk.CTkLabel(
    header,
    text="Remove image backgrounds using AI",
    font=("Arial", 14),
    text_color=GRAY
)
subtitle.pack(pady=5)

model_frame = ctk.CTkFrame(app, fg_color="transparent")
model_frame.pack(pady=(0, 5))

model_label = ctk.CTkLabel(
    model_frame,
    text="AI Model:",
    font=("Arial", 13),
    text_color=GRAY
)
model_label.pack(side="left", padx=(0, 10))

model_menu = ctk.CTkOptionMenu(
    model_frame,
    values=list(MODELS.keys()),
    width=210,
    fg_color="#292D38",
    button_color="#383D4A",
    button_hover_color=PURPLE
)
model_menu.set("birefnet-general")
model_menu.pack(side="left")

# =====================================
# MAIN CONTAINER
# =====================================
main_frame = ctk.CTkFrame(app, fg_color="transparent")
main_frame.pack(fill="both", expand=True, padx=30, pady=20)

main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_columnconfigure(1, weight=1)
main_frame.grid_rowconfigure(0, weight=1)

# =====================================
# ORIGINAL IMAGE PANEL
# =====================================
original_frame = ctk.CTkFrame(main_frame, fg_color=PANEL_COLOR, corner_radius=15)
original_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

original_title = ctk.CTkLabel(
    original_frame,
    text="Original Image",
    font=("Arial", 18, "bold")
)
original_title.pack(pady=20)

original_preview = ctk.CTkLabel(
    original_frame,
    text="Upload an image to start",
    text_color=GRAY,
    font=("Arial", 14),
    image=BLANK_IMAGE,
    compound="center"
)
original_preview.pack(fill="both", expand=True, padx=15, pady=15)

# =====================================
# RESULT IMAGE PANEL
# =====================================
result_frame = ctk.CTkFrame(main_frame, fg_color=PANEL_COLOR, corner_radius=15)
result_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

result_title = ctk.CTkLabel(
    result_frame,
    text="Result",
    font=("Arial", 18, "bold")
)
result_title.pack(pady=20)

result_preview = ctk.CTkLabel(
    result_frame,
    text="Result will appear here",
    text_color=GRAY,
    font=("Arial", 14),
    image=BLANK_IMAGE,
    compound="center"
)
result_preview.pack(fill="both", expand=True, padx=15, pady=15)

# =====================================
# STATUS LABEL
# =====================================
status_label = ctk.CTkLabel(
    app,
    text="Ready",
    font=("Arial", 13),
    text_color=GRAY
)
status_label.pack(pady=(5, 5))

# =====================================
# PROGRESS BAR + TIME LABEL
# =====================================
progress_bar = ctk.CTkProgressBar(
    app,
    width=350,
    height=8,
    corner_radius=10,
    progress_color=PURPLE,
    fg_color="#292D38",
    mode="indeterminate"
)

time_label = ctk.CTkLabel(
    app,
    text="",
    font=("Arial", 12),
    text_color=GRAY
)

# =====================================
# HELPERS
# =====================================
def get_preview_size(frame):
    app.update_idletasks()
    width = max(100, frame.winfo_width() - 50)
    height = max(100, frame.winfo_height() - 100)
    return (width, height)


def format_time(seconds):
    seconds = max(0, int(round(seconds)))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def show_progress():
    progress_bar.pack(pady=(5, 2), after=status_label)
    time_label.pack(pady=(0, 5), after=progress_bar)


def hide_progress():
    progress_bar.pack_forget()
    time_label.pack_forget()


# =====================================
# TIMER FUNCTIONS
# =====================================
def update_timer():
    global timer_job

    if not is_processing:
        return

    elapsed = time.time() - processing_start_time

    if estimated_seconds is not None:
        progress_bar.set(min(elapsed / estimated_seconds, 0.95))
        remaining = estimated_seconds - elapsed
        finish_clock = time.strftime(
            "%H:%M:%S",
            time.localtime(processing_start_time + estimated_seconds)
        )
        if remaining > 0:
            time_label.configure(
                text=(
                    f"⏱ {format_time(elapsed)} elapsed  •  "
                    f"~{format_time(remaining)} remaining  •  "
                    f"done at ~{finish_clock}"
                )
            )
        else:
            time_label.configure(
                text=f"⏱ {format_time(elapsed)} elapsed  •  almost done..."
            )
    else:
        time_label.configure(text=f"⏱ {format_time(elapsed)} elapsed")

    timer_job = app.after(200, update_timer)


def stop_timer():
    global timer_job
    if timer_job is not None:
        app.after_cancel(timer_job)
        timer_job = None
    progress_bar.stop()


# =====================================
# UPLOAD IMAGE FUNCTION
# =====================================
def upload_image():
    global selected_image
    global selected_megapixels
    global original_preview_image
    global result_image_path
    global result_image

    if is_processing:
        return

    file_path = filedialog.askopenfilename(
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")]
    )

    if not file_path:
        return

    try:
        image = Image.open(file_path)
        image = ImageOps.exif_transpose(image).convert("RGBA")
    except Exception as error:
        status_label.configure(
            text=f"Cannot open image: {error}",
            text_color=ERROR
        )
        return

    selected_image = file_path
    selected_megapixels = (image.width * image.height) / 1_000_000
    result_image_path = None
    result_image = None

    image.thumbnail(get_preview_size(original_frame))

    original_preview_image = ctk.CTkImage(
        light_image=image,
        dark_image=image,
        size=image.size
    )

    original_preview.configure(image=original_preview_image, text="")
    result_preview.configure(image=BLANK_IMAGE, text="Result will appear here")
    save_button.configure(state="disabled")

    status_label.configure(
        text="Image uploaded successfully",
        text_color=SUCCESS
    )


# =====================================
# REMOVE BACKGROUND FUNCTION
# =====================================
def remove_background():
    global is_processing
    global processing_start_time
    global estimated_seconds

    if is_processing:
        return

    if not selected_image:
        status_label.configure(
            text="Please upload an image first",
            text_color=ERROR
        )
        return

    model_key = MODELS[model_menu.get()]

    # Verifier que le model existe (bach ma ydirch download f --windowed)
    model_file = os.path.join(MODELS_DIR, f"{model_key}.onnx")
    if not os.path.exists(model_file):
        status_label.configure(
            text=f"Model file not found: {model_file}",
            text_color=ERROR
        )
        return

    is_processing = True

    remove_button.configure(state="disabled", text="Processing...")
    upload_button.configure(state="disabled")
    save_button.configure(state="disabled")
    model_menu.configure(state="disabled")

    if model_key in average_seconds_per_mp and model_key in ai_sessions:
        estimated_seconds = max(1.0, average_seconds_per_mp[model_key] * selected_megapixels)
        progress_bar.configure(mode="determinate")
        progress_bar.set(0)
    else:
        estimated_seconds = None
        progress_bar.configure(mode="indeterminate")
        progress_bar.start()

    show_progress()

    if model_key not in ai_sessions:
        status_label.configure(
            text=f"Loading AI model {model_key} (first time can take a while)...",
            text_color=ACCENT
        )
    else:
        status_label.configure(
            text="Removing background... Please wait",
            text_color=ACCENT
        )

    processing_start_time = time.time()
    update_timer()

    threading.Thread(
        target=process_image,
        args=(selected_image, model_key),
        daemon=True
    ).start()


# =====================================
# AI PROCESSING FUNCTION
# =====================================
def process_image(image_path, model_key):
    try:
        if model_key not in ai_sessions:
            ai_sessions[model_key] = new_session(model_key)
            app.after(
                0,
                lambda: status_label.configure(
                    text="Removing background... Please wait",
                    text_color=ACCENT
                )
            )

        input_image = Image.open(image_path)
        input_image = ImageOps.exif_transpose(input_image).convert("RGBA")

        inference_start = time.time()
        output_image = remove(input_image, session=ai_sessions[model_key])
        inference_seconds = time.time() - inference_start

        output_path = os.path.join(OUTPUT_DIR, "result.png")
        output_image.save(output_path)

        app.after(
            0,
            lambda: finish_processing(
                output_image,
                output_path,
                inference_seconds,
                model_key
            )
        )

    except Exception as error:
        error_message = str(error)
        app.after(0, lambda: processing_error(error_message))


# =====================================
# FINISH PROCESSING FUNCTION
# =====================================
def finish_processing(output_image, output_path, inference_seconds, model_key):
    global result_preview_image
    global result_image_path
    global result_image
    global is_processing
    global average_seconds_per_mp

    total_seconds = time.time() - processing_start_time

    is_processing = False
    stop_timer()
    hide_progress()

    if selected_megapixels > 0:
        new_value = inference_seconds / selected_megapixels
        if model_key not in average_seconds_per_mp:
            average_seconds_per_mp[model_key] = new_value
        else:
            average_seconds_per_mp[model_key] = (
                0.5 * average_seconds_per_mp[model_key] + 0.5 * new_value
            )

    result_image_path = output_path
    result_image = output_image

    preview = output_image.copy()
    preview.thumbnail(get_preview_size(result_frame))

    result_preview_image = ctk.CTkImage(
        light_image=preview,
        dark_image=preview,
        size=preview.size
    )

    result_preview.configure(image=result_preview_image, text="")

    status_label.configure(
        text=f"Background removed successfully in {format_time(total_seconds)}!",
        text_color=SUCCESS
    )

    remove_button.configure(state="normal", text="Remove Background")
    upload_button.configure(state="normal")
    model_menu.configure(state="normal")
    save_button.configure(state="normal")


# =====================================
# PROCESSING ERROR FUNCTION
# =====================================
def processing_error(error):
    global is_processing

    is_processing = False
    stop_timer()
    hide_progress()

    status_label.configure(text=f"Error: {error}", text_color=ERROR)

    remove_button.configure(state="normal", text="Remove Background")
    upload_button.configure(state="normal")
    model_menu.configure(state="normal")

    if result_image is not None:
        save_button.configure(state="normal")
    else:
        save_button.configure(state="disabled")


# =====================================
# SAVE IMAGE FUNCTION
# =====================================
def save_image():
    if result_image is None:
        status_label.configure(text="No result image to save", text_color=ERROR)
        return

    base_name = "my_image"
    if selected_image:
        base_name = os.path.splitext(os.path.basename(selected_image))[0] + "_nobg"

    save_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png")],
        initialfile=f"{base_name}.png"
    )

    if not save_path:
        return

    try:
        result_image.convert("RGBA").save(save_path, format="PNG")
        status_label.configure(text="Image saved successfully!", text_color=SUCCESS)
    except Exception as error:
        status_label.configure(text=f"Save error: {error}", text_color=ERROR)


# =====================================
# BUTTONS
# =====================================
buttons_frame = ctk.CTkFrame(app, fg_color="transparent")
buttons_frame.pack(pady=(5, 25))

upload_button = ctk.CTkButton(
    buttons_frame,
    text="Upload Image",
    width=150,
    height=42,
    corner_radius=10,
    fg_color="#292D38",
    hover_color="#383D4A",
    command=upload_image
)
upload_button.grid(row=0, column=0, padx=8)

remove_button = ctk.CTkButton(
    buttons_frame,
    text="Remove Background",
    width=180,
    height=42,
    corner_radius=10,
    fg_color=PURPLE,
    hover_color="#6D28D9",
    command=remove_background
)
remove_button.grid(row=0, column=1, padx=8)

save_button = ctk.CTkButton(
    buttons_frame,
    text="Save Image",
    width=150,
    height=42,
    corner_radius=10,
    fg_color="#292D38",
    hover_color="#383D4A",
    command=save_image,
    state="disabled"
)
save_button.grid(row=0, column=2, padx=8)

# =====================================
# START APPLICATION
# =====================================
app.mainloop()