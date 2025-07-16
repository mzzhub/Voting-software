# voting_machine.py

import os
import csv
import sys
import time
import threading
import winsound
import keyboard
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk

# ----------------- CONFIGURATION -----------------

# Staff PIN for Reset
STAFF_PIN = "1234"

# Toggle whether to show student symbol screen
ENABLE_STUDENT_SCREEN = True

# Beep settings
SHORT_BEEP_FREQ, SHORT_BEEP_DUR = 1000, 100  # Hz, ms
LONG_BEEP_FREQ, LONG_BEEP_DUR   = 1500, 1000  # Hz, ms


# CSV files
MAIN_CSV   = "votes.csv"
BACKUP_CSV = "backup_votes.csv"
SESSION_DATA_CSV = "session_data.csv"
TEMP_CSV   = "votes_temp.csv"

# Positions in fixed order
POSITIONS = [
    "Head Boy",
    "Sports Captain - Girl",
    "Arts Captain - Boy",
    "Arts Captain - Girl",
    "Co-curricular Activity Monitor - Boy",
    "Co-curricular Activity Monitor - Girl"
]

# Key → (Candidate, Position)
KEY_MAPPING = {
    "2":  ("Fahmi Hamdhan",    POSITIONS[0]),
    "3":  ("Rayan Muhammed VP",POSITIONS[0]),
    "5":  ("Bibi Bismil PK",   POSITIONS[1]),
    "6":  ("Fathima Marwa K",  POSITIONS[1]),
    "7":  ("Shiya Fathima",    POSITIONS[1]),
    "9":  ("Fizan E",          POSITIONS[2]),
    "0":  ("Shahrul Muhammed K",POSITIONS[2]),
    "-":  ("Siyan KP",         POSITIONS[2]),
    "\\": ("Azaza Subair",     POSITIONS[3]),
    "backspace": ("Faiza Firoz K", POSITIONS[3]),
    "home":      ("Alhadi Ansad K", POSITIONS[4]),
    "page up":   ("Muhammed Adhil", POSITIONS[4]),
    "/":         ("Aamiya Jamal",    POSITIONS[5]),
    "*":         ("Ayisha Nuha K",   POSITIONS[5]),
}

# --------------------------------------------------

class VotingMachine:
    def __init__(self):
        # --- PIN check at launch -----------------------------------
        temp_root = tk.Tk()
        temp_root.withdraw()
        pin = simpledialog.askstring("PIN Required", "Enter 4‑digit staff PIN to open control panel:", show="*")
        if pin != STAFF_PIN:
            messagebox.showerror("Error", "Incorrect PIN—exiting.")
            temp_root.destroy()
            sys.exit(1)
        temp_root.destroy()
        # -----------------------------------------------------------

        # --- State initialization ---
        self.voting_active = False
        self.votes = {}
        self.last_key = None
        self.hook = None

        # --- Session loading & auto‑creation ---
        self.total_students = 0
        self.session_names  = []
        self.session_counts = {}

        # 1) Read existing session rows (if any)
        rows = []
        if os.path.exists(SESSION_DATA_CSV):
            with open(SESSION_DATA_CSV, newline="") as sf:
                rows = [r for r in csv.reader(sf) if len(r) == 2]

        # 2) If we have past sessions, load them & create the next one
        if rows:
            for name, count in rows:
                self.session_names.append(name)
                self.session_counts[name] = int(count)
                self.total_students += int(count)

            last_num = int(self.session_names[-1].split()[-1])
            new_sess = f"Session {last_num + 1}"
            self.session_names.append(new_sess)
            self.session_counts[new_sess] = 0
            self.current_session = new_sess

        # 3) Otherwise, start fresh with only Session 1
        else:
            self.session_names   = ["Session 1"]
            self.session_counts  = {"Session 1": 0}
            self.current_session = "Session 1"

        # --- Prepare vote CSVs if missing ---
        for f in (MAIN_CSV, BACKUP_CSV):
            if not os.path.exists(f):
                with open(f, "w", newline="") as cf:
                    writer = csv.writer(cf)
                    writer.writerow(POSITIONS)

        # --- Build the GUIs ---
        self.build_staff_window()
        if ENABLE_STUDENT_SCREEN:
            self.build_student_window()


    def _save_session_data(self):
        with open(SESSION_DATA_CSV, "w", newline="") as sf:
            writer = csv.writer(sf)
            for name in self.session_names:
                writer.writerow([name, self.session_counts[name]])

    def on_close_request(self):
        pin = simpledialog.askstring(
            "PIN Required",
            "Enter 4‑digit staff PIN to exit:",
            show="*",
            parent=self.root
        )
        if pin == STAFF_PIN:
            if self.voting_active and self.votes:
                self._finalize_votes()
            self._save_session_data()
            self.root.destroy()
            os._exit(0)
        else:
            messagebox.showerror("Error", "Incorrect PIN", parent=self.root)
            # Window stays open



    def build_staff_window(self):
        self.root = tk.Tk()
        self.root.title("Staff Control Panel")

        # Intercept the window “X” close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_request)

        self.start_btn = tk.Button(self.root, text="Start Voting", width=20, command=self.start_voting)
        self.start_btn.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.reset_btn = tk.Button(self.root, text="Reset Voting", width=20, command=self.reset_voting)
        self.reset_btn.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Progress label (hidden until voting starts)
        self.progress_var = tk.StringVar()
        self.progress_label = tk.Label(self.root, textvariable=self.progress_var, font=("Arial", 14))
        # NOTE: no .grid() here!

        self.stop_btn = tk.Button(self.root, text="Save & Stop", width=20, command=self.save_and_stop)
        self.stop_btn.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        self.count_var = tk.StringVar(value=f"🧑‍🎓 Total Students Voted: {self.total_students}")
        tk.Label(self.root, textvariable=self.count_var, font=("Arial", 12)).grid(row=2, column=0, columnspan=3, sticky="w")

        self.session_var = tk.StringVar(value=f"🧾 Current Session: {self.current_session}")
        tk.Label(self.root, textvariable=self.session_var, font=("Arial", 12)).grid(row=3, column=0, columnspan=3, sticky="w")

        self.test_keyboard_btn = tk.Button(self.root, text="Test Keyboard", width=20, command=self.open_test_keyboard)
        self.test_keyboard_btn.grid(row=0, column=4, padx=10, pady=10, sticky="w")

        self.new_session_btn = tk.Button(self.root, text="New Session", width=20, command=self.increment_session)
        self.new_session_btn.grid(row=0, column=3, padx=10, pady=10, sticky="w")

        self.voting_status = tk.Label(self.root, text="", font=("Arial", 16, "bold"), fg="green")
        self.voting_status.grid(row=1, column=0, columnspan=4, pady=5, sticky="n")

        self.session_frame = tk.Frame(self.root)
        self.session_frame.grid(row=2, column=4, rowspan=4, padx=10, pady=10, sticky="ne")

        self.session_labels = {}
        self.update_session_display()

    def update_session_display(self):
        for widget in self.session_frame.winfo_children():
            widget.destroy()
        tk.Label(self.session_frame, text="🗂️ Session Counts", font=("Arial", 12, "bold")).pack()
        for name in self.session_names:
            label = tk.Label(self.session_frame, text=f"{name}: {self.session_counts[name]} students", font=("Arial", 11))
            label.pack(anchor="w")

    def increment_session(self):
        # Ask for PIN before allowing new session creation
        pin = simpledialog.askstring("PIN Required", "Enter 4-digit staff PIN to add a new session:", show="*")
        if pin != STAFF_PIN:
            messagebox.showerror("Error", "Incorrect PIN")
            return

        last_number = int(self.session_names[-1].split()[-1])
        new_session = f"Session {last_number + 1}"
        self.session_names.append(new_session)
        self.session_counts[new_session] = 0
        self.current_session = new_session
        self.session_var.set(f"🧾 Current Session: {self.current_session}")
        self.update_session_display()
        self._save_session_data()

    def save_and_stop(self):
        pin = simpledialog.askstring("PIN Required", "Enter 4‑digit staff PIN:", show="*")
        if pin != STAFF_PIN:
            messagebox.showerror("Error", "Incorrect PIN")
            return
        # finalize current votes if session is active
        if self.voting_active and len(self.votes) > 0:
            self._finalize_votes()
        try:
            if ENABLE_STUDENT_SCREEN:
                self.student_win.destroy()
        except:
            pass
        
        self._save_session_data()
        self.root.destroy()
        os._exit(0)  # hard exit to ensure keyboard unhooks

    def get_symbol_image(self, candidate):
        safe_name = candidate.replace(" ", "_")
        path = os.path.join("symbols", safe_name + ".png")  # or .png
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            img = img.resize((400, 400))  # adjust size as needed
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading symbol for {candidate}: {e}")
            return None
    

    def build_student_window(self):
        self.student_win = tk.Toplevel(self.root)
        self.student_win.title("Student Vote Display")
        self.student_win.configure(background="white")
        self.student_label = tk.Label(self.student_win, text="", font=("Arial", 48), bg="white")
        self.student_label.pack(expand=True, fill="both", padx=20, pady=20)
        self.student_win.withdraw()  # hide until voting starts

    def start_voting(self):
        self.voting_active = True
        self.votes.clear()

        # Show progress label
        self.progress_var.set("Votes cast: 0/6")
        self.progress_label.grid(row=1, column=0, columnspan=2, pady=10, sticky="w")
        self.start_btn.config(state=tk.DISABLED)

        # Show student screen (if enabled)
        if ENABLE_STUDENT_SCREEN:
            self.student_win.deiconify()
            self.student_label.config(image="", text="")  # clear any old content

        # Hook keyboard input
        self.hook = keyboard.on_press(self.on_key_press)

        # Disable session and stop buttons during voting
        self.new_session_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.test_keyboard_btn.config(state="disabled")


        # Show voting status
        self.voting_status.config(text="✅ Voting in Progress", fg="green")



    def reset_voting(self):
        pin = simpledialog.askstring("PIN Required", "Enter 4‑digit staff PIN:", show="*")
        if pin != STAFF_PIN:
            messagebox.showerror("Error", "Incorrect PIN")
            return
        self._cleanup_session()
        messagebox.showinfo("Reset", "Voting session has been reset.")

    def on_key_press(self, event):
        if not self.voting_active or event.event_type != "down":
            return
        name = event.name
        # disable long press
        if name == self.last_key:
            return
        self.last_key = name

        if name not in KEY_MAPPING:
            return

        candidate, position = KEY_MAPPING[name]
        if position in self.votes:
            return  # already voted this position

        # record vote
        self.votes[position] = candidate
        self._short_beep()
        self._save_temp()

        # update progress
        count = len(self.votes)
        self.progress_var.set(f"Votes cast: {count}/6")

        # student screen feedback
        if ENABLE_STUDENT_SCREEN:
            symbol = self.get_symbol_image(candidate)
            if symbol:
                self.student_label.config(image=symbol)
                self.student_label.image = symbol  # keep a reference
            else:
                self.student_label.config(text="(No symbol found)")
            self.student_win.after(2000, lambda: self.student_label.config(image="", text=""))

        # if done
        if count == len(POSITIONS):
            def delayed_finalize():
                self._long_beep()
                self._finalize_votes()
                self._end_session()

            delay = 2000 if ENABLE_STUDENT_SCREEN else 0
            self.root.after(delay, delayed_finalize)


    def _save_temp(self):
        # write current votes to temp CSV
        row = [ self.votes.get(pos, "") for pos in POSITIONS ]
        with open(TEMP_CSV, "w", newline="") as tf:
            csv.writer(tf).writerow(row)

    def _finalize_votes(self):
        # append to main and backup
        row = [ self.votes[pos] for pos in POSITIONS ]
        for f in (MAIN_CSV, BACKUP_CSV):
            with open(f, "a", newline="") as cf:
                csv.writer(cf).writerow(row)
        # remove temp
        try: os.remove(TEMP_CSV)
        except: pass

    def _cleanup_session(self):
        # ✅ 1. If voting was active and votes exist, finalize and exit early
        if self.voting_active and self.votes:
            self._finalize_votes()
            self._end_session()
            return  # Stop here so we don't double-clear or reset

        # ✅ 2. Otherwise, reset to blank state
        self.voting_active = False
        self.votes.clear()
        self.progress_var.set("Votes cast: 0/6")
        self.start_btn.config(state=tk.NORMAL)

        # ✅ 3. Keep student screen open and blank (if enabled)
        if ENABLE_STUDENT_SCREEN:
            self.student_label.config(image="", text="")

        # ✅ 4. Unhook keyboard if any
        if self.hook:
            keyboard.unhook(self.hook)
            self.hook = None

        self.last_key = None

        # ✅ 5. Re-enable buttons
        self.new_session_btn.config(state="normal")
        self.test_keyboard_btn.config(state="normal")

        # ✅ 6. Remove temporary vote file
        try:
            os.remove(TEMP_CSV)
        except:
            pass

    def open_test_keyboard(self):
        pin = simpledialog.askstring("PIN Required", "Enter 4-digit staff PIN to test keyboard:", show="*")
        if pin != STAFF_PIN:
            messagebox.showerror("Error", "Incorrect PIN")
            return

        # Create test window
        test_win = tk.Toplevel(self.root)
        test_win.title("Keyboard Test Mode")
        test_win.geometry("500x600")
        test_win.configure(bg="white")

        lbl_key = tk.Label(test_win, text="Press a key…", font=("Arial", 16, "bold"), bg="white")
        lbl_key.pack(pady=10)

        lbl_candidate = tk.Label(test_win, text="", font=("Arial", 14), bg="white")
        lbl_candidate.pack(pady=10)

        lbl_position = tk.Label(test_win, text="", font=("Arial", 14), bg="white")
        lbl_position.pack(pady=10)

        lbl_symbol = tk.Label(test_win, bg="white")
        lbl_symbol.pack(pady=20)

        # Function to handle key press in test mode
        def on_test_key(event):
            name = event.name
            lbl_key.config(text=f"Key: {name}")

            if name in KEY_MAPPING:
                candidate, position = KEY_MAPPING[name]
                lbl_candidate.config(text=f"Candidate: {candidate}")
                lbl_position.config(text=f"Position: {position}")

                symbol = self.get_symbol_image(candidate)
                if symbol:
                    lbl_symbol.config(image=symbol)
                    lbl_symbol.image = symbol
                else:
                    lbl_symbol.config(text="(No symbol)", image="")
                
                self._short_beep()

                # Reset after 2 seconds
                test_win.after(2000, lambda: (
                    lbl_key.config(text="Press a key…"),
                    lbl_candidate.config(text=""),
                    lbl_position.config(text=""),
                    lbl_symbol.config(image="", text="")
                ))
            else:
                lbl_candidate.config(text="Unknown key")
                lbl_position.config(text="")
                lbl_symbol.config(image="", text="")

        # Bind key press listener only for this window
        keyboard_hook = keyboard.on_press(on_test_key)

        # When closed, unhook
        def on_test_close():
            keyboard.unhook(keyboard_hook)
            test_win.destroy()

        test_win.protocol("WM_DELETE_WINDOW", on_test_close)


    def _end_session(self):
        # Mark voting as finished
        self.voting_active = False

        # Hide student window if enabled
        # Clear student screen if enabled
        if ENABLE_STUDENT_SCREEN:
            self.student_label.config(image="", text="")  # keep window open but blank

        # Unhook keyboard listener
        if self.hook:
            keyboard.unhook(self.hook)
            self.hook = None

        self.last_key = None
        self.votes.clear()

        # Increment total student count
        self.total_students += 1
        self.count_var.set(f"🧑‍🎓 Total Students Voted: {self.total_students}")

        # Update current session vote count
        self.session_counts[self.current_session] += 1
        self.update_session_display()

        # Re-enable staff buttons
        self.start_btn.config(state=tk.NORMAL)
        self.new_session_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.test_keyboard_btn.config(state="normal")


        # Clear voting status
        self.voting_status.config(text="")

        # Hide the progress count
        self.progress_label.grid_remove()
        self._save_session_data()





    def _short_beep(self):
        threading.Thread(target=lambda: winsound.Beep(SHORT_BEEP_FREQ, SHORT_BEEP_DUR), daemon=True).start()

    def _long_beep(self):
        threading.Thread(target=lambda: winsound.Beep(LONG_BEEP_FREQ, LONG_BEEP_DUR), daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    VotingMachine().run()
