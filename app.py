import sys

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from odoo_manager.gui import MainWindow

KEY = "OdooManager-single-instance"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Odoo Manager")
    app.setQuitOnLastWindowClosed(False)

    # only one copy: if already running, ask it to show its window
    sock = QLocalSocket()
    sock.connectToServer(KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(KEY)
    server = QLocalServer()
    server.listen(KEY)

    state = {}

    def create(tray=False):
        win = MainWindow(start_in_tray=tray)
        win.relaunch.connect(lambda: QTimer.singleShot(0, relaunch))
        state["win"] = win

    def relaunch():
        old = state["win"]
        geo = old.saveGeometry()
        old.dispose()
        create()
        state["win"].restoreGeometry(geo)

    create(tray="--tray" in sys.argv)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), state["win"].show_window()))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
