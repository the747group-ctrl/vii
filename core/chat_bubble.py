"""
VII Chat Bubble — Floating text panel near the orb.
Shows transcript (what you said) and response (what VII said).
Auto-fades after a few seconds.

Developed by The 747 Lab
"""

import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen


class ChatBubble(QWidget):
    """Floating chat bubble that appears near the orb."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._transcript = ""
        self._response = ""
        self._opacity = 0.0
        self._target_opacity = 0.0
        self._max_width = 320
        self._padding = 14
        self._visible_timer = QTimer()
        self._visible_timer.setSingleShot(True)
        self._visible_timer.timeout.connect(self.fade_out)

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(33)

        self.setFixedSize(self._max_width + 20, 200)
        self.hide()

    def show_transcript(self, text, orb_pos):
        """Show what the user said."""
        self._transcript = text
        self._response = ""
        self._position_near(orb_pos)
        self._target_opacity = 1.0
        self.show()
        self.raise_()
        self.update()

    def show_response(self, text, orb_pos):
        """Show VII's response."""
        self._response = text[:200]
        self._position_near(orb_pos)
        self._target_opacity = 1.0
        self.show()
        self.raise_()
        self.update()
        # Auto-fade after response
        self._visible_timer.start(6000)

    def fade_out(self):
        self._target_opacity = 0.0

    def _position_near(self, orb_pos):
        """Position bubble above the orb."""
        x = orb_pos.x() - self.width() // 2
        y = orb_pos.y() - self.height() - 10
        # Keep on screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(10, min(x, screen.width() - self.width() - 10))
        y = max(10, y)
        self.move(x, y)

    def _animate(self):
        if abs(self._opacity - self._target_opacity) > 0.01:
            self._opacity += (self._target_opacity - self._opacity) * 0.15
            self.setWindowOpacity(self._opacity)
            if self._opacity < 0.02 and self._target_opacity == 0.0:
                self.hide()
                self._transcript = ""
                self._response = ""
            self.update()

    def paintEvent(self, event):
        if not self._transcript and not self._response:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pad = self._padding
        w = self.width() - 20
        y_offset = 10

        # Measure text heights
        font_small = QFont("Helvetica", 11)
        font_body = QFont("Helvetica", 12)
        p.setFont(font_small)

        # Calculate total height needed
        total_h = pad * 2
        if self._transcript:
            total_h += 18
        if self._response:
            # Word wrap the response
            lines = self._wrap_text(p, self._response, font_body, w - pad * 2)
            total_h += len(lines) * 18 + (8 if self._transcript else 0)

        # Background rounded rect
        bg_rect = QRect(10, y_offset, w, min(total_h, self.height() - 20))
        path = QPainterPath()
        path.addRoundedRect(float(bg_rect.x()), float(bg_rect.y()),
                            float(bg_rect.width()), float(bg_rect.height()), 12, 12)
        p.fillPath(path, QColor(15, 15, 22, 230))
        p.setPen(QPen(QColor(40, 40, 60), 1))
        p.drawPath(path)

        # Transcript (what you said)
        y = y_offset + pad
        if self._transcript:
            p.setFont(font_small)
            p.setPen(QColor(120, 120, 140))
            p.drawText(QRect(10 + pad, y, w - pad * 2, 18),
                       Qt.AlignmentFlag.AlignLeft, f'You: "{self._transcript[:60]}"')
            y += 22

        # Response (what VII said)
        if self._response:
            p.setFont(font_body)
            p.setPen(QColor(200, 200, 210))
            lines = self._wrap_text(p, self._response, font_body, w - pad * 2)
            for line in lines[:6]:
                p.drawText(QRect(10 + pad, y, w - pad * 2, 18),
                           Qt.AlignmentFlag.AlignLeft, line)
                y += 18

        p.end()

    def _wrap_text(self, painter, text, font, max_width):
        """Simple word wrap."""
        painter.setFont(font)
        fm = painter.fontMetrics()
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = current + (" " if current else "") + word
            if fm.horizontalAdvance(test) > max_width:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        return lines
