"""Test script for debugging toolbar tools"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt

# Import our modules
from ui.toolbar import AnnotationToolbar, ToolMode
from ui.pdf_viewer import PDFViewer, ToolMode as ViewerToolMode

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tool Test")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Status label
        self.status = QLabel("Click a tool button...")
        layout.addWidget(self.status)

        # Annotation toolbar
        self.toolbar = AnnotationToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        # Connect signal
        self.toolbar.tool_changed.connect(self.on_tool_changed)

        # PDF Viewer
        self.viewer = PDFViewer()
        layout.addWidget(self.viewer)

        # Also connect tool_changed to viewer
        self.toolbar.tool_changed.connect(self.on_tool_to_viewer)

    def on_tool_changed(self, tool: str):
        self.status.setText(f"Tool changed signal received: {tool}")
        print(f"Tool changed: {tool}")

    def on_tool_to_viewer(self, tool: str):
        try:
            mode = ViewerToolMode(tool)
            self.viewer.set_tool_mode(mode)
            print(f"Viewer tool mode set to: {mode}")
        except Exception as e:
            print(f"Error setting viewer tool mode: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()

    print("Click on different tools in the toolbar to test...")
    print("Check if 'Tool changed:' messages appear.")

    sys.exit(app.exec())
