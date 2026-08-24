"""
网络对战配置与房间管理对话框 (模块1/模块2)
提供房间创建、加入、端口配置、IP输入、执子选择及状态展示
"""
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QButtonGroup, QSpinBox,
    QGroupBox, QMessageBox, QDialogButtonBox
)
from PySide6.QtCore import Qt


class OnlineMatchDialog(QDialog):
    """网络对战配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 网络对战大厅 (Online PvP)")
        self.setMinimumWidth(440)
        
        is_light = False
        if parent and hasattr(parent, "control_bar") and hasattr(parent.control_bar, "theme_combo"):
            is_light = (parent.control_bar.theme_combo.currentText() == "浅色")

        if is_light:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                }
                QLabel {
                    color: #334155;
                    font-size: 13px;
                }
                QGroupBox {
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #0284c7;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QLineEdit, QSpinBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QRadioButton {
                    color: #334155;
                    font-size: 13px;
                    spacing: 6px;
                }
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    padding: 7px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton#btnCancel {
                    background-color: #e2e8f0;
                    color: #334155;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #0b0f19;
                    color: #f1f5f9;
                }
                QLabel {
                    color: #cbd5e1;
                    font-size: 13px;
                }
                QGroupBox {
                    border: 1px solid #334155;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #38bdf8;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QLineEdit, QSpinBox {
                    background-color: #1e293b;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QRadioButton {
                    color: #cbd5e1;
                    font-size: 13px;
                    spacing: 6px;
                }
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    padding: 7px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton#btnCancel {
                    background-color: #334155;
                }
            """)

        self.result_data: Dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 16, 18, 16)

        title = QLabel("网络双人对战配置")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8;")
        layout.addWidget(title)

        desc = QLabel("支持局域网或互联网对弈，房主建立房间，对手输入 IP 与端口加入。")
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 模式选择: 房主 vs 加入
        mode_box = QGroupBox("角色选择")
        mode_layout = QHBoxLayout(mode_box)
        self.rb_host = QRadioButton("创建房间 (作为房主)")
        self.rb_join = QRadioButton("加入已有房间 (作为客方)")
        self.rb_host.setChecked(True)
        self.rb_host.toggled.connect(self._on_role_toggled)

        self.role_group = QButtonGroup(self)
        self.role_group.addButton(self.rb_host)
        self.role_group.addButton(self.rb_join)
        mode_layout.addWidget(self.rb_host)
        mode_layout.addWidget(self.rb_join)
        layout.addWidget(mode_box)

        # 网络参数
        net_box = QGroupBox("网络连接参数")
        net_layout = QVBoxLayout(net_box)
        net_layout.setSpacing(10)

        ip_row = QHBoxLayout()
        self.lbl_ip = QLabel("房主 IP 地址:")
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_input.setEnabled(False)  # 房主无需输入 IP
        ip_row.addWidget(self.lbl_ip)
        ip_row.addWidget(self.ip_input, stretch=1)
        net_layout.addLayout(ip_row)

        port_row = QHBoxLayout()
        lbl_port = QLabel("通信端口:")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(8765)
        port_row.addWidget(lbl_port)
        port_row.addWidget(self.port_spin, stretch=1)
        net_layout.addLayout(port_row)

        layout.addWidget(net_box)

        # 执子选择
        side_box = QGroupBox("选择执子方")
        side_layout = QHBoxLayout(side_box)
        self.rb_white = QRadioButton("执白 (White) 先手")
        self.rb_black = QRadioButton("执黑 (Black) 后手")
        self.rb_white.setChecked(True)
        self.side_group = QButtonGroup(self)
        self.side_group.addButton(self.rb_white)
        self.side_group.addButton(self.rb_black)
        side_layout.addWidget(self.rb_white)
        side_layout.addWidget(self.rb_black)
        layout.addWidget(side_box)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_confirm = QPushButton("开始对战")
        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

    def _on_role_toggled(self, is_host: bool):
        self.ip_input.setEnabled(not is_host)
        if is_host:
            self.lbl_ip.setText("监听绑定 IP:")
            self.ip_input.setText("0.0.0.0")
            self.rb_white.setChecked(True)
        else:
            self.lbl_ip.setText("房主 IP 地址:")
            self.ip_input.setText("127.0.0.1")
            self.rb_black.setChecked(True)

    def _on_confirm(self):
        is_host = self.rb_host.isChecked()
        ip = self.ip_input.text().strip()
        port = self.port_spin.value()
        my_side = "white" if self.rb_white.isChecked() else "black"

        if not is_host and not ip:
            QMessageBox.warning(self, "提示", "请输入有效的房主 IP 地址！")
            return

        self.result_data = {
            "is_host": is_host,
            "host": ip or ("0.0.0.0" if is_host else "127.0.0.1"),
            "port": port,
            "my_side": my_side,
        }
        self.accept()

    @staticmethod
    def get_online_config(parent=None) -> Optional[Dict[str, Any]]:
        dialog = OnlineMatchDialog(parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.result_data
        return None
