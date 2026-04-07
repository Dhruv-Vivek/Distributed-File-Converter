import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os

# Import your existing function
from client import convert_file

# ─── GUI App ─────────────────────────────
class FileConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("File Converter (Client)")
        self.root.geometry("400x250")

        self.file_path = ""

        # Title
        tk.Label(root, text="Distributed File Converter", font=("Arial", 14, "bold")).pack(pady=10)

        # Select file button
        tk.Button(root, text="Select File", command=self.select_file).pack(pady=5)

        self.file_label = tk.Label(root, text="No file selected")
        self.file_label.pack()

        # Extension input
        tk.Label(root, text="Output Extension (.pdf, .json, .csv)").pack(pady=5)
        self.ext_entry = tk.Entry(root)
        self.ext_entry.pack()

        # Convert button
        tk.Button(root, text="Convert", command=self.start_conversion).pack(pady=10)

        # Status
        self.status_label = tk.Label(root, text="")
        self.status_label.pack()

    def select_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.file_path = path
            self.file_label.config(text=os.path.basename(path))

    def start_conversion(self):
        if not self.file_path:
            messagebox.showerror("Error", "Please select a file")
            return

        ext = self.ext_entry.get()
        if not ext:
            messagebox.showerror("Error", "Enter output extension")
            return

        self.status_label.config(text="Processing... ⏳")

        # Run in thread (so GUI doesn’t freeze)
        threading.Thread(target=self.run_conversion, args=(ext,), daemon=True).start()

    def run_conversion(self, ext):
        try:
            result = convert_file(self.file_path, ext)

            if result and result["status"] == "success":
                self.status_label.config(text="✅ Success!")
                
                # Auto open file
                os.startfile(result["output_path"])

            else:
                self.status_label.config(text="❌ Failed")

        except Exception as e:
            self.status_label.config(text="❌ Error")
            print(e)

# ─── Run App ─────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = FileConverterGUI(root)
    root.mainloop()