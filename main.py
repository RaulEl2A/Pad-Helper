import tkinter as tk
from ui.main_window import PadHelperApp


def main() -> None:
    root = tk.Tk()
    app = PadHelperApp(root)
    app.run()


if __name__ == "__main__":
    main()