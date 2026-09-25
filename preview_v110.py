"""Functional 1.1.0 development UI; released entry point remains unchanged."""
import sys, os, json
from pathlib import Path

from src.macos_appearance import configure_native_appearance
configure_native_appearance()

from PySide6.QtCore import QLocale, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QDoubleValidator
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMessageBox,
    QVBoxLayout, QWidget, QPushButton, QButtonGroup, QStackedWidget, QGridLayout,
)

import spaceman_icc_bridge_qt as existing
from src.build_standard import build_standard_pair, rgb_matrix

# Preview interactions must not replace the working app's saved preferences.
existing.S = existing.S.copy()
existing.CFG = existing.CFG.with_name('config-v110.json')
if existing.CFG.exists():
    try: existing.S.update(json.loads(existing.CFG.read_text(encoding='utf-8')))
    except (ValueError, OSError): pass

# CIE 1931 xy; gamut and tone-curve choices are independent.
GAMUT_PRESETS = {
    'sRGB': ((.64, .33), (.30, .60), (.15, .06), (.3127, .3290)),
    'Adobe RGB (1998)': ((.64, .33), (.21, .71), (.15, .06), (.3127, .3290)),
    'Display P3': ((.68, .32), (.265, .69), (.15, .06), (.3127, .3290)),
}
WHITE_PRESETS = {'D65': (.3127, .3290), 'D50': (.3457, .3585), 'Custom': None}


class StandardWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, args, parent):
        super().__init__(parent)
        self.args = args

    def run(self):
        try:
            build_standard_pair(**self.args)
            self.completed.emit(str(self.args['output'])+'\n'+str(self.args['mhc2_output']))
        except Exception as e:
            self.failed.emit(str(e))


class PreviewWindow(existing.Window):
    def __init__(self):
        self.standard_mode = False
        self.busy = False
        super().__init__()
        self.setWindowTitle('SpaceMan ICC Bridge')
        root = self.centralWidget().layout()
        self.source_sections = {}
        self.source_headings = {}

        # Wrap the existing source rows without changing their file interactions.
        for index, key in enumerate(('bcs_dir', 'cube_dir', 'icc_dir')):
            if index:
                root.takeAt(0)  # Existing between-section spacer.
            heading_item = root.takeAt(0)
            list_item = root.takeAt(0)
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            heading = heading_item.layout()
            self.source_headings[key] = heading.itemAt(0).widget()
            layout.addLayout(heading)
            layout.addWidget(list_item.widget(), 1)
            self.source_sections[key] = section

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons = []
        for index, title in enumerate(('Measurement', 'Standard')):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setMinimumHeight(28)
            corner = 'left' if index == 0 else 'right'
            button.setStyleSheet(
                'QPushButton{color:#888;border:1px solid #606060;padding:4px 12px;'
                f'border-top-{corner}-radius:6px;border-bottom-{corner}-radius:6px;'
                '}QPushButton:checked{background:#5a5a5a;color:#fff;}'
                'QPushButton:hover:!checked{background:#404040;}'
            )
            self.mode_group.addButton(button, index)
            self.mode_buttons.append(button)
            mode_row.addWidget(button, 1)
        self.mode_buttons[0].setChecked(True)
        mode_row.setContentsMargins(0, 0, 0, 14)
        root.insertLayout(0, mode_row)

        # Both pages share the same reserved space, keeping ICC/output stationary.
        self.upper = QStackedWidget()
        measurement = QWidget()
        measurement_layout = QVBoxLayout(measurement)
        measurement_layout.setContentsMargins(0, 0, 0, 0)
        measurement_layout.setSpacing(14)
        for key in ('bcs_dir', 'cube_dir'):
            measurement_layout.addWidget(self.source_sections[key], 1)
        self.upper.addWidget(measurement)

        self.options = QWidget()
        options = QVBoxLayout(self.options)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(8)
        self.gamut = QComboBox()
        self.gamut.addItems([*GAMUT_PRESETS, 'Custom'])
        self.gamut.setToolTip('Target gamut for Windows MHC2. The regular ICC describes the actual display gamut for color-managed applications; white point and gamma apply to both outputs.')
        # One grid owns all alignment: label | preset | x/value | y.
        coordinates = QGridLayout()
        coordinates.setHorizontalSpacing(10)
        coordinates.setVerticalSpacing(6)
        coordinates.setColumnMinimumWidth(0, 90)
        for column in (1, 2, 3):
            coordinates.setColumnStretch(column, 1)
        coordinates.addWidget(QLabel('Target Gamut'), 0, 0)
        coordinates.addWidget(self.gamut, 0, 1)
        coordinates.addWidget(QLabel('x'), 0, 2)
        coordinates.addWidget(QLabel('y'), 0, 3)
        self.gamut.setMinimumWidth(0)
        self.gamut.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.gamut.setMinimumContentsLength(8)
        self.xy_fields = {}
        for row, point in enumerate('RGB', 1):
            coordinates.addWidget(QLabel(point), row, 1, Qt.AlignmentFlag.AlignRight)
            for column, axis in enumerate('xy', 2):
                edit = existing.SelectAllLineEdit()
                validator = QDoubleValidator(0.0, 1.0, 6, edit)
                validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                validator.setLocale(QLocale.c())
                edit.setValidator(validator)
                edit.setAccessibleName(f'{point} {axis}')
                edit.textEdited.connect(self.custom_gamut)
                coordinates.addWidget(edit, row, column)
                self.xy_fields[point, axis] = edit
        options.addLayout(coordinates)

        coordinates.setRowMinimumHeight(4, 4)
        coordinates.addWidget(QLabel('White Point'), 5, 0)
        self.white = QComboBox()
        self.white.addItems(WHITE_PRESETS)
        coordinates.addWidget(self.white, 5, 1)
        for column, axis in enumerate('xy', 2):
            edit = existing.SelectAllLineEdit()
            validator = QDoubleValidator(0.0, 1.0, 6, edit)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            validator.setLocale(QLocale.c())
            edit.setValidator(validator)
            edit.setAccessibleName(f'White {axis}')
            edit.textEdited.connect(self.custom_white)
            self.xy_fields['W', axis] = edit
            coordinates.addWidget(edit, 5, column)
        self.white.currentTextChanged.connect(self.apply_white)
        self.apply_white('D65')

        self.tone = QComboBox()
        self.tone.addItems(['Gamma 2.2', 'Gamma 1.8', 'Gamma 2.4', 'Gamma 2.6', 'sRGB', 'Custom'])
        coordinates.addWidget(QLabel('Gamma'), 6, 0)
        coordinates.addWidget(self.tone, 6, 1)
        self.gamma = existing.SelectAllLineEdit('2.2')
        gamma_validator = QDoubleValidator(0.1, 10.0, 8, self.gamma)
        gamma_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        gamma_validator.setLocale(QLocale.c())
        self.gamma.setValidator(gamma_validator)
        self.gamma.textEdited.connect(self.custom_gamma)
        self.last_gamma = '2.2'
        coordinates.addWidget(self.gamma, 6, 2, 1, 2)
        for control in (self.gamut, self.white, self.tone, self.gamma, *self.xy_fields.values()):
            control.setFixedHeight(26)
        self.gamut.currentTextChanged.connect(self.apply_gamut)
        self.tone.currentTextChanged.connect(self.apply_tone)
        self.apply_gamut('sRGB')
        options.addStretch(1)
        self.upper.addWidget(self.options)
        root.insertWidget(1, self.upper, 2)
        root.insertSpacing(2, 14)
        root.insertWidget(3, self.source_sections['icc_dir'], 1)

        footer = root.itemAt(root.count() - 1).layout()
        self.mode_group.idClicked.connect(self.switch_mode)
        self.switch_mode()

    def apply_gamut(self, name):
        if name in GAMUT_PRESETS:
            for point, xy in zip('RGB', GAMUT_PRESETS[name]):
                for axis, value in zip('xy', xy):
                    self.xy_fields[point, axis].setText(f'{value:.4f}')

    def custom_gamut(self, *_):
        self.gamut.setCurrentText('Custom')

    def apply_white(self, name):
        values = WHITE_PRESETS[name]
        if values is not None:
            for axis, value in zip('xy', values):
                self.xy_fields['W', axis].setText(f'{value:.4f}')

    def custom_white(self, *_):
        self.white.setCurrentText('Custom')

    def apply_tone(self, name):
        if name == 'sRGB':
            self.last_gamma = self.gamma.text() or self.last_gamma
            self.gamma.clear()
            self.gamma.setPlaceholderText('sRGB piecewise curve')
            self.gamma.setEnabled(False)
        else:
            self.gamma.setEnabled(True)
            self.gamma.setPlaceholderText('Enter gamma')
            if name.startswith('Gamma '):
                self.gamma.setText(name.split(' ', 1)[1])
            elif not self.gamma.text():
                self.gamma.setText(self.last_gamma)

    def custom_gamma(self, *_):
        self.last_gamma = self.gamma.text()
        self.tone.setCurrentText('Custom')

    def switch_mode(self, *_):
        self.standard_mode = self.mode_group.checkedId() == 1
        self.upper.setCurrentIndex(1 if self.standard_mode else 0)
        self.source_headings['icc_dir'].setText('Display.icc' if self.standard_mode else 'Spaceman.icc')
        self.ready()

    def ready(self):
        if not hasattr(self, 'generate'):
            return
        keys = ('icc_dir',) if self.standard_mode else tuple(self.boxes)
        self.generate.setEnabled(
            not self.busy and all(self.selected(self.boxes[key]) for key in keys)
            and bool(self.name.text().strip()) and bool(self.out.text().strip())
        )

    def run(self):
        if self.busy: return
        try:
            name = self.name.text().strip()
            if not name or name in ('.','..') or any(c in name for c in '<>:"/\\|?*') or any(ord(c)<32 for c in name) or name.endswith(('.', ' ')):
                raise ValueError('Please enter a valid output name without file-path characters.')
            if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
                raise ValueError('This output name is reserved by Windows.')
            folder=Path(self.out.text().strip())
            if not self.standard_mode:
                name=''.join(x if x.isalnum() or x in '._-' else '_' for x in name)
            suffixes=['.icc','-mhc2.icc']
            if any((folder/(name+s)).exists() for s in suffixes):
                raise ValueError('Output already exists. Choose a new output name.')
            if not self.standard_mode:
                return super().run()
            if any(not e.hasAcceptableInput() for e in self.xy_fields.values()):
                raise ValueError('Enter valid numeric xy coordinates.')
            points={p:tuple(float(self.xy_fields[p,a].text()) for a in 'xy') for p in 'RGBW'}
            primaries=tuple(points[p] for p in 'RGB')
            rgb_matrix(primaries,points['W'])
            gamma=None if self.tone.currentText()=='sRGB' else float(self.gamma.text())
            source=self.selected(self.boxes['icc_dir'])
            if not source or not self.out.text().strip(): raise ValueError('Select a display ICC and output folder.')
            exe=existing.APP/'tools'/'mhc2gen'/('MHC2Gen.exe' if os.name=='nt' else 'MHC2Gen')
            args=dict(source=source,output=folder/(name+'.icc'),mhc2_output=folder/(name+'-mhc2.icc'),exe=exe,primaries=primaries,white=points['W'],gamma=gamma)
            self.busy=True; self.timer.stop(); self.centralWidget().setEnabled(False)
            self.generate.setText('Generating…')
            self.worker=StandardWorker(args,self)
            self.worker.completed.connect(lambda p: QMessageBox.information(self,'Complete','Created:\n'+p))
            self.worker.failed.connect(lambda message: QMessageBox.critical(self,'Generation failed',message))
            self.worker.finished.connect(self.generation_finished)
            self.worker.start()
        except Exception as e:
            QMessageBox.critical(self,'Generation failed',str(e))

    def generation_finished(self):
        self.busy=False; self.centralWidget().setEnabled(True)
        self.generate.setText('Generate'); self.timer.start(2000); self.ready()

    def closeEvent(self, event):
        if self.busy: event.ignore()
        else: super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(existing.APP / 'assets' / 'icon-sp.png')))
    window = PreviewWindow()
    window.show()
    if '--smoke-test' in sys.argv:
        import tempfile
        from PySide6.QtCore import QTimer
        def smoke_test():
            try:
                window.mode_buttons[1].click()
                assert window.standard_mode
                assert window.windowTitle() == 'SpaceMan ICC Bridge'
                assert (window.width(), window.height()) == (560, 560)
                with tempfile.TemporaryDirectory(prefix='bridge-smoke-') as tmp:
                    build_standard_pair('/System/Library/ColorSync/Profiles/AdobeRGB1998.icc', Path(tmp)/'smoke.icc', Path(tmp)/'smoke-mhc2.icc', existing.APP/'tools/mhc2gen/MHC2Gen', white=(.3457,.3585), gamma=2.2)
                print('PASS: packaged UI, Standard mode, native MHC2Gen and D50/gamma 2.2 generation', flush=True)
                app.exit(0)
            except Exception as e:
                print('FAIL:',str(e),flush=True)
                app.exit(1)
        QTimer.singleShot(300,smoke_test)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
