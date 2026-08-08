import os
import winreg
import ctypes
import sys
import mss
import time
from threading import Thread, Event
from datetime import datetime
from pathlib import Path
import numpy as np
import cv2
import pyautogui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                            QLabel, QHBoxLayout, QWidget, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QRect, pyqtSignal, QSize
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QIcon


def is_dark_mode_enabled():
    """Checks the Windows' dark mode. """
    try:
        reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(reg_key, "AppsUseLightTheme")
        winreg.CloseKey(reg_key)
        return value == 0  # if the value is 
    except Exception as e:
        return False
        
        
def set_dark_titlebar(self, enable: bool):
    hwnd = int(self.winId())
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20

    value = ctypes.c_int(enable)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        ctypes.byref(value),
        ctypes.sizeof(value)
        )        


class ScreenCaptureApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screenshoot")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().availableGeometry()

        # calculates the middle of the screen
        x = (screen.width() - 900) // 2
        y = (screen.height() - 120) // 2

        # sets the window size and position 
        self.resize(900, 120)
        self.move(x, y)
     
        pictures_dir = Path(os.path.expanduser("~/Pictures"))

        # Creates the folder 'Screenshots' in the Pictures directory - this is where the screenshots will be saved 
        self.screenshots_dir = pictures_dir / "Screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Variables for selection
        self.selection_start = None
        self.selection_end = None
        self.selection_active = False
        self.capture_window = None
        
        # Variables for recording 
        self.recording = False
        self.video_writer = None
        self.recording_thread = None
        self.stop_event = Event()
        self.frame_rate = 15  # recording framerate
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        layout = QHBoxLayout()
        

        
        self.btn_screenshot = QPushButton()
        self.btn_screenshot.setFixedSize(80, 80)
        self.btn_screenshot.setStyleSheet("background: none")
        self.btn_screenshot.setIcon(QIcon("whole.png"))
        self.btn_screenshot.setIconSize(QSize(80, 80))
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        layout.addWidget(self.btn_screenshot)
        
        self.btn_select_area = QPushButton()
        self.btn_select_area.setFixedSize(80, 80)
        self.btn_select_area.setStyleSheet("background: none")
        self.btn_select_area.setIcon(QIcon("crop.png"))
        self.btn_select_area.setIconSize(QSize(80, 80))
        self.btn_select_area.clicked.connect(self.start_area_selection)
        layout.addWidget(self.btn_select_area)
        
        self.separator = QFrame()
        self.separator.setFixedWidth(2)
        self.separator.setFixedHeight(80)
        layout.addWidget(self.separator)
        
        self.btn_record = QPushButton()
        self.btn_record.setFixedSize(80, 80)
        self.btn_record.setStyleSheet("background: none")
        self.btn_record.setIcon(QIcon("record.png"))
        self.btn_record.setIconSize(QSize(80, 80))
        self.btn_record.clicked.connect(self.toggle_recording)
        layout.addWidget(self.btn_record)
        
        self.separator2 = QFrame()
        self.separator2.setFixedWidth(2)
        self.separator2.setFixedHeight(80)
        layout.addWidget(self.separator2)
        
        self.close_button = QPushButton()
        self.close_button.setFixedSize(60, 60)
        self.close_button.setStyleSheet("background: none")
        self.close_button.setIcon(QIcon("close.png"))
        self.close_button.setIconSize(QSize(40, 40))
        self.close_button.clicked.connect(self.close)  
        layout.addWidget(self.close_button)
        
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        if is_dark_mode_enabled():
            central_widget.setStyleSheet("background-color: rgba(50, 50, 50, 246); border-radius: 20px;")
            self.separator.setStyleSheet("border: 1px solid  #494949")
            self.separator2.setStyleSheet("border: 1px solid  #494949")
        else: 
            central_widget.setStyleSheet("background-color: rgba(234, 234, 234, 246); border-radius: 20px;")
            self.separator.setStyleSheet("border: 1px solid #d7d7d7")
            self.separator2.setStyleSheet("border: 1px solid #d7d7d7")
    
    def take_screenshot(self):
        self.hide()
        time.sleep(0.3)  # waits for the window to disappear so its not on the screenshot
        
        try:
            screenshot = pyautogui.screenshot()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.screenshots_dir, f"screenshot_{timestamp}.png")
            screenshot.save(filename)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Couldn't take a screenshot: {e}")
        finally:
            self.show()  # the window shows again after taking the screenshot
    
    def start_area_selection(self):
        self.hide()
        time.sleep(0.3)
        
        self.capture_window = AreaSelectionWindow()
        self.capture_window.selection_completed.connect(self.handle_area_selection)
        self.capture_window.selection_cancelled.connect(self.cancel_area_selection)
        self.capture_window.showFullScreen()
    
    def handle_area_selection(self, rect):
        self.capture_window.close()
        self.capture_window = None
        time.sleep(0.3)  # same here

        # additional time, sometimes needed if a computer is slower 
        time.sleep(0.5)
        
        if rect:
            try:
                # first take a screenshot
                full_screenshot = pyautogui.screenshot()
                # then crop
                x, y, w, h = rect
                if w > 0 and h > 0:
                    cropped_screenshot = full_screenshot.crop((x, y, x + w, y + h))
                else:
                    QMessageBox.warning(self, "Warning", "The chosen area is too small.")
                    return

                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(self.screenshots_dir, f"screenshot_cropped_{timestamp}.png")
                cropped_screenshot.save(filename)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Couldn't take a screenshot: {e}")
        
        self.show()


    
    def cancel_area_selection(self):
        self.capture_window.close()
        self.show()

    
    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        self.recording = True
        self.stop_event.clear()
        self.btn_record.setIcon(QIcon("stop.png"))
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screen_size = (monitor["width"], monitor["height"])
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.screenshots_dir, f"recording_{timestamp}.mp4")
        self.video_writer = cv2.VideoWriter(filename, fourcc, self.frame_rate, screen_size)
        self.recording_thread = Thread(target=self.record_screen)
        self.recording_thread.start()

    
    def record_screen(self):
        frame_time = 1.0 / self.frame_rate
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # the main monitor window
            while not self.stop_event.is_set():
                start_time = time.time()

                img = sct.grab(monitor)
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self.video_writer.write(frame)
                
                elapsed = time.time() - start_time
                time_to_wait = frame_time - elapsed
                if time_to_wait > 0:
                    time.sleep(time_to_wait)

   
    def stop_recording(self):
        self.recording = False
        self.stop_event.set()
        
        if self.recording_thread:
            self.recording_thread.join()
        if self.video_writer:
            self.video_writer.release()
        
        self.btn_record.setIcon(QIcon("record.png"))
        

        msg = QMessageBox(self)
        msg.setWindowIcon(QIcon("s.ico"))
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Done")
        msg.setText("Screen recording saved.")

        ok_button = msg.addButton("OK", QMessageBox.AcceptRole)
        ok_button.setMinimumWidth(120)

        if is_dark_mode_enabled():
            set_dark_titlebar(msg, True)
            msg.setStyleSheet('''
            
                QWidget {
                    background-color: #202020; 
                    color: #c8c8c8;
                }                
                QPushButton {
                    background-color: #61605f; 
                    border: 1px solid #727170;
                    border-radius: 8px;
                    font-size: 23px;
                    padding-left: 25px;
                    padding-right: 25px;
                    padding-top: 6px;
                    padding-bottom: 6px;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #0064e1; 
                    border: 1px solid #0071ff;
                    color: white;
                }
            ''')
        else:
            set_dark_titlebar(msg, False)
            msg.setStyleSheet('''   

                QWidget {
                    background-color: #f3f3f3;
                    color: black;
                }

                QPushButton {
                    background-color: white; 
                    border: 1px solid #cccccc;
                    border-radius: 8px;
                    font-size: 23px;
                    padding-left: 25px;
                    padding-right: 25px;
                    padding-top: 6px;
                    padding-bottom: 6px;
                    color: black;
                }


                QPushButton:pressed {
                    background-color: #0064e1;
                    border: 1px solid #001c40;
                    color: white;
                }

            ''')            
            

        msg.exec_()


class AreaSelectionWindow(QWidget):
    selection_completed = pyqtSignal(object)
    selection_cancelled = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        self.start_point = None
        self.end_point = None
        self.selection_rect = None
        
        self.overlay = QPixmap(pyautogui.size().width, pyautogui.size().height)
        self.overlay.fill(QColor(100, 100, 100, 100))
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.overlay)
        
        if self.selection_rect:
            painter.setPen(QPen(Qt.darkGray, 2))
            painter.drawRect(self.selection_rect)
            
            painter.fillRect(self.selection_rect, QColor(0, 0, 0, 0))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point)
            self.update()
    
    def mouseMoveEvent(self, event):
        if self.start_point:
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.start_point:
            self.end_point = event.pos()
            rect = QRect(self.start_point, self.end_point).normalized()
            
            screen_rect = QRect(
                self.mapToGlobal(rect.topLeft()),
                self.mapToGlobal(rect.bottomRight())
            )
            
            self.selection_completed.emit((
                screen_rect.x(),
                screen_rect.y(),
                screen_rect.width(),
                screen_rect.height()
            ))
            self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScreenCaptureApp()
    window.show()
    sys.exit(app.exec_())