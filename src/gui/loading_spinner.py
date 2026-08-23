"""
现代极简 Loading Spinner 加载动效控件 (模块1 - GUI)
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen


class LoadingSpinner(QWidget):
    """现代极简圆形旋转动效指示器"""

    def __init__(self, parent=None, size: int = 24, color: str = "#38bdf8"):
        super().__init__(parent)
        self.spinner_size = size
        self.color = QColor(color)
        self.angle = 0
        self.setFixedSize(size, size)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.setInterval(30)  # ~33 fps 平滑旋转

    def _rotate(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def start(self):
        if not self.timer.isActive():
            self.timer.start()
            self.show()

    def stop(self):
        if self.timer.isActive():
            self.timer.stop()
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(self.color, 2.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        margin = 3.0
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        # 绘制背景淡色静态圆环
        bg_pen = QPen(QColor(self.color.red(), self.color.green(), self.color.blue(), 40), 2.5)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        # 绘制动态旋转圆弧
        painter.setPen(pen)
        # spanAngle 单位为 1/16 度，负值顺时针
        painter.drawArc(rect, int(-self.angle * 16), int(100 * 16))
