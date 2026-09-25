import json, subprocess, sys, os
from build_device import build_device
from src.build_mhc2_from_cube import apply_cube_gray_to_mhc2
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QLabel,QLineEdit,QPushButton,QListWidget,QFileDialog,QMessageBox,QVBoxLayout,QHBoxLayout,QMenu
APP=Path(__file__).resolve().parent
if os.name == 'nt':
 CFG=Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SpaceMan ICC Bridge' / 'config.json'
else:
 CFG=Path.home()/'Library'/'Application Support'/'SpaceMan ICC Bridge'/'config.json'
 OLD_CFG=Path.home()/'SpaceMan ICC Bridge'/'config.json'
 if not CFG.exists() and OLD_CFG.exists():
  CFG.parent.mkdir(parents=True,exist_ok=True); CFG.write_bytes(OLD_CFG.read_bytes())
DESKTOP=Path.home()/'Desktop'; D={'bcs_dir':str(DESKTOP),'icc_dir':str(DESKTOP),'output_dir':str(DESKTOP)}
try: S={**D,**json.loads(CFG.read_text(encoding='utf-8'))}
except Exception: S=D.copy()
def save():
 try:
  CFG.parent.mkdir(parents=True,exist_ok=True); CFG.write_text(json.dumps(S,ensure_ascii=False,indent=2),encoding='utf-8')
 except OSError:
  pass
class DropList(QListWidget):
 def __init__(self,callback): super().__init__(); self.callback=callback; self.setAcceptDrops(True)
 def _hover(self,on):
  self.setProperty('dragActive',on); self.style().unpolish(self); self.style().polish(self); self.update()
 def dragEnterEvent(self,e):
  if e.mimeData().hasUrls(): self._hover(True); e.acceptProposedAction()
 def dragMoveEvent(self,e):
  if e.mimeData().hasUrls(): e.acceptProposedAction()
 def dragLeaveEvent(self,e): self._hover(False); e.accept()
 def dropEvent(self,e):
  paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
  self._hover(False)
  if paths: self.callback(paths); e.acceptProposedAction()
class DropPath(QLineEdit):
 def __init__(self,callback): super().__init__(); self.callback=callback; self.setAcceptDrops(True); self._edit_original=''
 def mouseDoubleClickEvent(self,e):
  self._edit_original=self.text(); self.setReadOnly(False); self.setStyleSheet('QLineEdit{color:#fff} QLineEdit[dragActive="true"]{background:#30343a;border:2px solid #88a8c8}'); super().mouseDoubleClickEvent(e); self.selectAll()
 def finish_edit(self,commit=True):
  if self.isReadOnly(): return
  if not commit: self.setText(self._edit_original)
  else:
   p=self.text().strip()
   if p: S['output_dir']=p; save()
  self.setReadOnly(True); self.setStyleSheet('QLineEdit{color:#888} QLineEdit[dragActive="true"]{background:#30343a;border:2px solid #88a8c8}')
 def keyPressEvent(self,e):
  if e.key()==Qt.Key.Key_Escape:
   self.finish_edit(False); self.clearFocus(); return
  if e.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
   self.finish_edit(True); self.clearFocus(); return
  super().keyPressEvent(e)
 def focusOutEvent(self,e):
  super().focusOutEvent(e); self.finish_edit(True)
 def _hover(self,on):
  self.setProperty('dragActive',on); self.style().unpolish(self); self.style().polish(self); self.update()
 def dragEnterEvent(self,e):
  if any(u.isLocalFile() for u in e.mimeData().urls()): self._hover(True); e.acceptProposedAction()
 def dragMoveEvent(self,e):
  if any(u.isLocalFile() for u in e.mimeData().urls()): e.acceptProposedAction()
 def dragLeaveEvent(self,e): self._hover(False); e.accept()
 def dropEvent(self,e):
  self._hover(False); folders=[Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile() and Path(u.toLocalFile()).is_dir()]
  if folders: self.finish_edit(True); self.callback(str(folders[0])); e.acceptProposedAction()
class WorkArea(QWidget):
 def __init__(self,window): super().__init__(); self.window=window; self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
 def mousePressEvent(self,e):
  if hasattr(self.window,'out'): self.window.out.finish_edit(True); self.window.setFocus()
  super().mousePressEvent(e)
class SelectAllLineEdit(QLineEdit):
 def __init__(self,text=''):
  super().__init__(text); self._select_on_click=True
 def focusOutEvent(self,e):
  self._select_on_click=True; super().focusOutEvent(e)
 def mousePressEvent(self,e):
  from PySide6.QtCore import QTimer
  select=self._select_on_click; self._select_on_click=False
  super().mousePressEvent(e)
  if select: QTimer.singleShot(0,self.selectAll)
class Window(QMainWindow):
 def __init__(self):
  super().__init__(); self.setWindowTitle('SpaceMan ICC Bridge'); self.resize(560,560); self.setMinimumSize(560,560)
  self.vars={k:QLineEdit(S.get(k,str(DESKTOP))) for k in ('bcs_dir','icc_dir','cube_dir','output_dir')}; self.boxes={}; c=WorkArea(self); self.setCentralWidget(c); root=QVBoxLayout(c); root.setContentsMargins(20,16,20,16); root.setSpacing(0)
  for label,key,ext in (('Profile.bpc / CSV / TI3','bcs_dir',('.bpc','.bcs','.csv','.ti3')),('LUT.cube','cube_dir',('.cube',)),('Spaceman.icc','icc_dir',('.icc','.icm'))):
   if self.boxes: root.addSpacing(14)
   hr=QHBoxLayout(); hr.setContentsMargins(0,0,0,4); heading=QLabel(label); heading.setStyleSheet('font-size:13px;font-weight:bold;'); hr.addWidget(heading); hr.addStretch(); fb=QPushButton('…'); fb.setFixedWidth(42); fb.clicked.connect(lambda _=False,k=key,e=ext:self.choose_source(k,e)); hr.addWidget(fb); root.addLayout(hr); box=DropList(lambda paths,k=key,e=ext:self.drop_source(k,e,paths)); box.setMinimumHeight(62); box.setSizePolicy(box.sizePolicy().horizontalPolicy(),box.sizePolicy().verticalPolicy().Expanding); box.setSelectionMode(QListWidget.SelectionMode.SingleSelection); box.itemSelectionChanged.connect(self.ready); box.itemSelectionChanged.connect(lambda k=key:self.sync_name(k)); box.setStyleSheet('QListWidget{color:#888} QListWidget[dragActive="true"]{background:#30343a;border:2px solid #88a8c8} QListWidget::item{color:#888;padding:2px 4px} QListWidget::item:selected{background:#5a5a5a;color:#fff} QListWidget::item:selected:!active{background:#5a5a5a;color:#fff}'); root.addWidget(box,1); self.boxes[key]=box
  root.addSpacing(18); row=QHBoxLayout(); row.setSpacing(10); row.addWidget(QLabel('Output Name')); self.name=SelectAllLineEdit('Output'); self.name_user_edited=False; self.name.textEdited.connect(lambda _text:self.mark_name_edited()); self.name.textChanged.connect(self.ready); row.addWidget(self.name,1); root.addLayout(row); root.addSpacing(8)
  row=QHBoxLayout(); row.setSpacing(10); row.addWidget(QLabel('Output Folder')); self.out=DropPath(self.set_output); self.out.setText(S['output_dir']); self.out.setReadOnly(True); self.out.setStyleSheet('QLineEdit{color:#888} QLineEdit[dragActive="true"]{background:#30343a;border:2px solid #88a8c8}'); row.addWidget(self.out,1); self.ob=QPushButton('…'); self.ob.setFixedWidth(42); self.ob.clicked.connect(self.choose_output); row.addWidget(self.ob); root.addLayout(row)
  bottom=QHBoxLayout(); bottom.setContentsMargins(0,8,0,0); bottom.addStretch(); self.generate=QPushButton('Generate'); self.generate.clicked.connect(self.run); bottom.addWidget(self.generate); root.addLayout(bottom); self.statusBar().hide(); self.refresh(); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(2000)
 def choose_source(self,key,ext):
  p=QFileDialog.getExistingDirectory(self,'Select folder',self.vars[key].text())
  if p: self.vars[key].setText(p); S[key]=p; save(); self.refresh()
 def drop_source(self,key,ext,paths):
  folders=[Path(p) for p in paths if Path(p).is_dir()]
  if folders:
   self.vars[key].setText(str(folders[0])); S[key]=str(folders[0]); save(); self.refresh(); return
  exts=(ext,) if isinstance(ext,str) else ext
  valid=[Path(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() in exts]
  if not valid: return
  self.vars[key].setText(str(valid[0].parent)); S[key]=str(valid[0].parent); save(); self.refresh(); b=self.boxes[key]; p=str(valid[0]);
  if p in getattr(b,'_paths',[]): b.setCurrentRow(b._paths.index(p))
  if key=='icc_dir' and not self.name_user_edited: self.name.setText(valid[0].stem)
 def choose_output(self):
  p=QFileDialog.getExistingDirectory(self,'Select folder',self.out.text())
  if p: self.out.setText(p); S['output_dir']=p; save()
 def set_output(self,p): self.out.setText(p); S['output_dir']=p; save()
 def mark_name_edited(self): self.name_user_edited=bool(self.name.text().strip())
 def sync_name(self,key):
  if key=='icc_dir' and not self.name_user_edited:
   p=self.selected(self.boxes[key])
   if p: self.name.setText(Path(p).stem)
 def refresh(self):
  for key,ext in (('bcs_dir',('.bpc','.bcs','.csv','.ti3')),('cube_dir',('.cube',)),('icc_dir',('.icc','.icm'))):
   b=self.boxes[key]; old=self.selected(b); d=Path(self.vars[key].text()); valid_dir=d.is_dir(); exts=(ext,) if isinstance(ext,str) else ext; fs=sorted((p for e in exts for p in d.rglob('*'+e) if p.is_file()),key=lambda p:p.name.casefold()) if valid_dir else []; paths=[str(p) for p in fs]; marker=None if valid_dir and fs else ('No compatible files found' if valid_dir else 'Please select a folder')
   display_paths=paths+([marker] if marker else [])
   if display_paths!=getattr(b,'_display_paths',[]):
    b.clear(); b._paths=paths; b._display_paths=display_paths; [b.addItem(p.name) for p in fs]
    if marker:
     b.addItem(marker); item=b.item(b.count()-1); item.setFlags(Qt.ItemFlag.NoItemFlags); item.setForeground(Qt.GlobalColor.gray)
    b.setCurrentRow(paths.index(old) if old in paths else -1)
  self.ready()
 def selected(self,b):
  i=b.currentRow(); p=getattr(b,'_paths',[]); return p[i] if 0<=i<len(p) else ''
 def ready(self): self.generate.setEnabled(all(self.selected(self.boxes[k]) for k in self.boxes) and bool(self.name.text().strip()) and bool(self.out.text().strip()))
 def run(self):
  try:
   b,r=[self.selected(self.boxes[k]) for k in ('bcs_dir','icc_dir')]
   n=''.join(x if x.isalnum() or x in '._-' else '_' for x in self.name.text().strip())
   if not n or n in ('.','..'): raise ValueError('Please enter an output name.')
   if os.name == 'nt' and n.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}: raise ValueError('This output name is reserved by Windows.')
   out=Path(self.out.text()); ordinary=out/f'{n}.icc'; mhc=out/f'{n}-mhc2.icc'
   if Path(r).resolve() in (ordinary.resolve(),mhc.resolve()): raise ValueError('Choose an output folder or name that does not overwrite the raw ICC.')
   exe=APP/'tools'/'mhc2gen'/('MHC2Gen.exe' if os.name == 'nt' else 'MHC2Gen')
   if not exe.is_file(): raise FileNotFoundError(f'MHC2Gen is missing: {exe}')
   out.mkdir(parents=True,exist_ok=True)
   build_device(b,r,ordinary)
   result=subprocess.run([str(exe),'sdr-csc','--source-gamut=sRGB','--keep-whitepoint=Bradford','--profile-desc',mhc.name,str(ordinary),str(mhc)],cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
   if result.returncode: raise RuntimeError(result.stderr or result.stdout or f'MHC2Gen exited with code {result.returncode}')
   if not mhc.is_file(): raise RuntimeError('MHC2Gen did not create the output profile.')
   apply_cube_gray_to_mhc2(mhc, self.selected(self.boxes['cube_dir']), mhc)
   QMessageBox.information(self,'Complete',f'Created:\n{ordinary}\n{mhc}')
  except Exception as e: QMessageBox.critical(self,'Generation failed',str(e))

def main():
 app=QApplication(sys.argv); icon=APP/'assets'/'icon-sp.png'; app.setWindowIcon(QIcon(str(icon))) if icon.exists() else None; w=Window(); w.show(); sys.exit(app.exec())
