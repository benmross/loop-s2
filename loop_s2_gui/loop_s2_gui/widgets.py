"""The pieces of the console that draw themselves."""

import math

from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QFrame, QHeaderView, QLabel, QPlainTextEdit, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from loop_s2_gui import theme
from loop_s2_gui.simulation import (ACTIVE, LIGHT_BLUE, LIGHT_FLASHING_GREEN, LIGHT_RED,
                                    REACHED, SKIPPED, STATUS_NAMES, TYPE_NAMES)

STATUS_COLORS = {ACTIVE: theme.INFO, REACHED: theme.OK, SKIPPED: theme.DIM}


def panel(title=None):
    """A bordered box with an optional heading, used for every section."""
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setObjectName('panelTitle')
        layout.addWidget(label)
    return frame, layout


class SignalLight(QWidget):
    """The LED on the back of the rover, mirrored on the operator's screen.

    The rules put a light on the rover so a judge at the course can see what
    it is doing. The operator cannot see the course, so they get the same
    light here: red autonomous, blue teleoperated, flashing green on arrival.
    """

    def __init__(self):
        super().__init__()
        self.setFixedSize(54, 54)
        self._state = 0
        self._on = True
        timer = QTimer(self)
        timer.timeout.connect(self._blink)
        timer.start(380)

    def _blink(self):
        if self._state == LIGHT_FLASHING_GREEN:
            self._on = not self._on
            self.update()
        elif not self._on:
            self._on = True
            self.update()

    def set_state(self, state):
        if state != self._state:
            self._state = state
            self._on = True
            self.update()

    def color(self):
        return {LIGHT_RED: QColor(theme.FAULT), LIGHT_BLUE: QColor(theme.INFO),
                LIGHT_FLASHING_GREEN: QColor(theme.OK)}.get(self._state, QColor('#39424f'))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = self.color()
        lit = self._on and self._state != 0
        p.setPen(QPen(QColor(theme.EDGE), 2))
        p.setBrush(QBrush(color if lit else color.darker(320)))
        p.drawEllipse(QRectF(9, 9, 36, 36))
        if lit:
            glow = QColor(color)
            glow.setAlpha(55)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QRectF(2, 2, 50, 50))


class StatusTile(QFrame):
    """One number an operator watches, with the state it is in."""

    def __init__(self, title, sub=''):
        super().__init__()
        self.setObjectName('panel')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 9)
        layout.setSpacing(1)
        self._title = QLabel(title.upper())
        self._title.setObjectName('tileTitle')
        self._value = QLabel('--')
        self._value.setObjectName('tileValue')
        self._sub = QLabel(sub)
        self._sub.setObjectName('tileSub')
        for widget in (self._title, self._value, self._sub):
            layout.addWidget(widget)

    def set(self, value, state='ok', sub=None):
        self._value.setText(str(value))
        self._value.setStyleSheet(f'color: {theme.STATE_COLORS.get(state, theme.TEXT)};')
        if sub is not None:
            self._sub.setText(sub)

    def blank(self, sub=None):
        """No fresh data. Show it, rather than leaving a stale number up."""
        self.set('--', 'idle', sub)


class MapView(QWidget):
    """Plan view of the course, from the base station outwards.

    This is the operator's only picture of where the rover is, so it shows
    the legs with their arrival tolerances, where the rover has actually
    been, and nothing else.
    """

    def __init__(self):
        super().__init__()
        self.setMinimumSize(460, 420)
        self.legs = []
        self.rover = None
        self.trail = []
        self.stale = False
        self.target = None

    def set_legs(self, legs):
        self.legs = legs
        self.update()

    def set_rover(self, east, north, heading_deg, target=None):
        self.rover = (east, north, heading_deg)
        self.target = target
        if not self.trail or math.dist(self.trail[-1], (east, north)) > 1.5:
            self.trail.append((east, north))
            del self.trail[:-1500]
        self.update()

    def set_stale(self, stale):
        if stale != self.stale:
            self.stale = stale
            self.update()

    def _transform(self):
        xs, ys = [0.0], [0.0]
        for leg in self.legs:
            xs.append(leg['east'])
            ys.append(leg['north'])
        if self.rover:
            xs.append(self.rover[0])
            ys.append(self.rover[1])
        pad = 40.0
        minx, maxx = min(xs) - pad, max(xs) + pad
        miny, maxy = min(ys) - pad, max(ys) + pad
        margin = 26
        scale = min((self.width() - 2 * margin) / max(maxx - minx, 1.0),
                    (self.height() - 2 * margin) / max(maxy - miny, 1.0))
        offx = (self.width() - (maxx - minx) * scale) / 2
        offy = (self.height() - (maxy - miny) * scale) / 2

        def to_px(east, north):
            return (offx + (east - minx) * scale, self.height() - offy - (north - miny) * scale)

        return to_px, scale

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#0b0f14'))
        to_px, scale = self._transform()
        dim = 0.45 if self.stale else 1.0

        def colour(hex_color, alpha=255):
            c = QColor(hex_color)
            c.setAlpha(int(alpha * dim))
            return c

        # Range rings every 100 m from the base station, so distance from home
        # is readable without measuring.
        p.setPen(QPen(colour(theme.EDGE, 150), 1, Qt.DotLine))
        bx, by = to_px(0, 0)
        for metres in range(100, 900, 100):
            r = metres * scale
            p.drawEllipse(QRectF(bx - r, by - r, 2 * r, 2 * r))

        if self.rover and self.target is not None:
            tx, ty = to_px(*self.target)
            rx, ry = to_px(self.rover[0], self.rover[1])
            p.setPen(QPen(colour(theme.INFO, 110), 1, Qt.DashLine))
            p.drawLine(int(rx), int(ry), int(tx), int(ty))

        if len(self.trail) > 1:
            p.setPen(QPen(colour(theme.INFO, 170), 2))
            points = [to_px(e, n) for e, n in self.trail]
            p.drawPolyline(QPolygonF([_pt(x, y) for x, y in points]))

        font = QFont(theme.MONO, 8)
        p.setFont(font)
        for leg in self.legs:
            x, y = to_px(leg['east'], leg['north'])
            color = colour(STATUS_COLORS.get(leg['status'], theme.WARN))
            radius = max(leg['tolerance'] * scale, 5.0)
            p.setPen(QPen(color, 2 if leg['status'] == ACTIVE else 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))
            p.setBrush(QBrush(color))
            p.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
            p.setPen(QPen(colour(theme.TEXT, 210)))
            # Labels go left of their marker near the right edge, where they
            # would otherwise run off the panel.
            if x > self.width() * 0.78:
                width = p.fontMetrics().width(leg['label'])
                p.drawText(int(x - radius - 5 - width), int(y + 4), leg['label'])
            else:
                p.drawText(int(x + radius + 5), int(y + 4), leg['label'])

        p.setPen(QPen(colour(theme.DIM), 2))
        p.setBrush(QBrush(colour('#243040')))
        p.drawRect(QRectF(bx - 6, by - 6, 12, 12))
        p.setPen(QPen(colour(theme.DIM)))
        p.drawText(int(bx + 11), int(by + 4), 'BASE')

        if self.rover:
            x, y = to_px(self.rover[0], self.rover[1])
            p.save()
            p.translate(x, y)
            p.rotate(self.rover[2])
            p.setPen(QPen(colour(theme.TEXT), 1))
            p.setBrush(QBrush(colour(theme.WARN if self.stale else theme.OK)))
            p.drawPolygon(QPolygonF([_pt(0, -11), _pt(7, 8), _pt(0, 4), _pt(-7, 8)]))
            p.restore()

        # Scale bar, because a picture without one invites bad guesses.
        bar = 100 * scale
        p.setPen(QPen(colour(theme.DIM), 2))
        p.drawLine(14, self.height() - 16, int(14 + bar), self.height() - 16)
        p.drawText(int(18 + bar), self.height() - 12, '100 m')
        p.drawText(14, 20, 'N ^')

        if self.stale:
            p.setPen(QPen(QColor(theme.FAULT), 2))
            p.setFont(QFont('DejaVu Sans', 15, QFont.Bold))
            box = QRectF(0, self.height() / 2 - 26, self.width(), 52)
            p.fillRect(box, QColor(20, 8, 8, 205))
            p.drawText(box, Qt.AlignCenter, 'POSITION NOT CURRENT')


def _pt(x, y):
    from PyQt5.QtCore import QPointF
    return QPointF(x, y)


class LegTable(QTableWidget):
    """The mission plan: every leg, its coordinates and where it stands."""

    HEADERS = ['#', 'TARGET', 'TYPE', 'LATITUDE', 'LONGITUDE', 'TOL', 'STATUS']

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.setMinimumHeight(210)

    def set_legs(self, legs):
        keep = self.currentRow()
        if self.rowCount() != len(legs):
            self.setRowCount(len(legs))
        for row, leg in enumerate(legs):
            values = [str(leg['id'] + 1), leg['label'], TYPE_NAMES[leg['kind']],
                      f"{leg['latitude']:.5f}", f"{leg['longitude']:.5f}",
                      f"{leg['tolerance']:.0f} m", STATUS_NAMES[leg['status']]]
            for column, value in enumerate(values):
                item = self.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(row, column, item)
                if item.text() != value:
                    item.setText(value)
                if column == len(values) - 1:
                    item.setForeground(QColor(STATUS_COLORS.get(leg['status'], theme.DIM)))
        if keep >= 0:
            self.setCurrentCell(keep, 0)
        elif legs:
            self.setCurrentCell(0, 0)

    def selected_leg(self):
        row = self.currentRow()
        return row if row >= 0 else None


class EventLog(QPlainTextEdit):
    """Everything the operator did and everything the rover answered."""

    LEVELS = {'info': theme.TEXT, 'ok': theme.OK, 'warn': theme.WARN, 'fault': theme.FAULT,
              'sent': theme.INFO}

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumBlockCount(400)
        self.setMinimumHeight(120)

    def log(self, clock, text, level='info'):
        color = self.LEVELS.get(level, theme.TEXT)
        self.appendHtml(
            f'<span style="color:{theme.DIM}">{clock}</span> '
            f'<span style="color:{color}">{text}</span>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
