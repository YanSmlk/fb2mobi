#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import cssutils
import codecs
import time
import subprocess
import webbrowser
import logging
import tempfile
import shutil

from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QTreeWidgetItem, 
                            QMessageBox, QDialog, QWidget, QLabel, QAbstractItemView, 
                            QSizePolicy, QAction, QMenu, QProgressDialog)
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QFont, QFontMetrics, 
                        QStandardItem, QStandardItemModel)
from PyQt5.QtCore import (QObject, QThread, pyqtSignal, QEvent, Qt, QTranslator, 
                        QLocale, QCoreApplication, QTimer, QSize, QRectF, QByteArray, 
                        QBuffer, QPoint)

from ui.MainWindow import Ui_MainWindow
from ui.AboutDialog import Ui_AboutDialog
from ui.SettingsDialog import Ui_SettingsDialog
from ui.OpenGDriveDialog import Ui_GDriveDialog
from ui.RenameDialog import Ui_RenameDialog

from ui.gui_config import GuiConfig
import ui.images_rc
import ui.ui_version
import ui.genres
from ui.ebookmeta import EbookMeta
from ui.fontdb import FontDb
from ui.gdrive import GoogleDrive

from modules.config import ConverterConfig
from modules.sendtokindle import SendToKindle
from modules.utils import format_pattern, copy_file
import modules.default_css
import fb2mobi
import synccovers
import version

TREE_LIST_CSS_ACTIVE = "selection-color: white; selection-background-color: #386CDA; alternate-background-color: #F3F6FA;"
TREE_LIST_CSS_UNACTIVE = "selection-color: black; selection-background-color: #D4D4D4; alternate-background-color: #F3F6FA;"

SUPPORT_URL = u'http://www.the-ebook.org/forum/viewtopic.php?t=30380'
HELP_URL = u'https://github.com/rupor-github/fb2mobi/wiki'

PROCESS_MODE_CONVERT = 0
PROCESS_MODE_KINDLE = 1
PROCESS_MODE_MAIL = 3

_translate = QCoreApplication.translate


class RenameDialog(QDialog, Ui_RenameDialog):
    def __init__(self, parent, author_pattern, filename_pattern, dest_dir, delete_after_rename, files):
        super(RenameDialog, self).__init__(parent)
      
        self.files = files
        self.setupUi(self)
        self.switch_copy_to()
        self.lineAuthorPattern.setText(author_pattern)
        self.lineFilenamePattern.setText(filename_pattern)
        self.checkDeleteAfterRename.setCheckState(delete_after_rename)
        if dest_dir:
            self.lineDestFolder.setText(dest_dir)
            self.radioRenameTo.setChecked(True)
        self.switch_copy_to()

        self.lineAuthorPattern.setToolTip(( '<b>Возможные значения:</b><br/>'
                                            '<b>#f</b> - имя<br/>'
                                            '<b>#m</b> - отчество<br/>'
                                            '<b>#l</b> - фамилия<br/>'
                                            '<b>#fi</b> - инициал имени<br/>'
                                            '<b>#mi</b> - инициал отчества'))

        self.lineFilenamePattern.setToolTip((   '<b>Возможные значения:</b><br/>'
                                                '<b>#author</b> - автор<br/>'
                                                '<b>#authors</b> - авторы<br/>'
                                                '<b>#title</b> - название книги<br/>'
                                                '<b>#series</b> - название серии<br/>'
                                                '<b>#number</b> - номер в серии<br/>'
                                                '<b>#abbrseries</b> - аббревиатура названия серии<br/>'
                                                '<b>#translator</b> - переводчик<br/>'
                                                '<b>{}</b> - блок'))

    def test(self):
        self.textSamples.clear()        
        dest_dir = ''
        if self.radioRenameTo.isChecked():
            dest_dir = self.lineDestFolder.text()
        for file in self.files:
            try:
                meta = EbookMeta(file)
                meta.get()
                new_file = meta.meta_to_filename(self.lineAuthorPattern.text(), 
                    self.lineFilenamePattern.text(),
                    dest_path=dest_dir)
                self.textSamples.append(new_file)
            except:
                self.textSamples.append(_translate('fb2mobi-gui', 'Renaming error for file {0}'.format(file)))

    def switch_copy_to(self):
        if self.radioSameDir.isChecked():
            self.lineDestFolder.setEnabled(False)
            self.buttonSelectFolder.setEnabled(False)
        else:
            self.lineDestFolder.setEnabled(True)
            self.buttonSelectFolder.setEnabled(True)

    def select_dest_dir(self):
        dlgPath = QFileDialog(self, _translate('fb2mobi-gui', 'Select folder'))
        dlgPath.setFileMode(QFileDialog.Directory)
        dlgPath.setOption(QFileDialog.ShowDirsOnly, True)

        if dlgPath.exec_():
            for d in dlgPath.selectedFiles():
                self.lineDestFolder.setText(os.path.normpath(d))

class GDriveDialog(QDialog, Ui_GDriveDialog):
    def __init__(self, parent, credential_file, executable_path):
        super(GDriveDialog, self).__init__(parent)
        self.setupUi(self)
        self.credential_file = credential_file
        self.executable_path = executable_path

        self.model = QStandardItemModel(self.tree)
        self.tree.setModel(self.model)
        self.tree.expanded.connect(self.update_model)
        self.tree.setIconSize(QSize(24, 24))
        self.gdrive = GoogleDrive(self.credential_file, self.executable_path)

        self.selected_files = []

        self.init_model()

    def init_model(self):
        file_list = self.gdrive.list('root')

        for file in file_list:
            item = self.create_item(file)
            if (item.data()['type'] == 'folder' or item.text().lower().endswith('.fb2.zip')
                or item.text().lower().endswith('.fb2') or item.text().lower().endswith('.epub')):
                self.model.appendRow(item)

    def update_model(self, index):
        parent = self.model.itemFromIndex(index)
        data = parent.data()
        if data['type'] == 'folder' and not data['loaded']: 
            parent.removeRow(0)
            file_list = self.gdrive.list(data['id'])            
            for file in file_list:
                item = self.create_item(file)
                if (item.data()['type'] == 'folder' or item.text().lower().endswith('.fb2.zip')
                    or item.text().lower().endswith('.fb2') or item.text().lower().endswith('.epub')):
                    parent.appendRow(item)

            data['loaded'] = True
            parent.setData(data)

    def create_item(self, file):
        item = QStandardItem(file['name'])
        if file['mimeType'].lower().endswith('.folder'):
            node_type = 'folder'
            icon = QIcon(':/Images/folder.png')
        else:
            node_type = 'file'
            icon = QIcon(':/Images/file.png')
        item.setData({'type': node_type, 'id':file['id'], 'loaded': False})
        item.setIcon(icon)
        if node_type == 'folder':
            child_item = QStandardItem(_translate('fb2mobi-gui', 'Loading...'))
            item.appendRow(child_item)

        return item

    def done(self, result):
        if result == QDialog.Accepted:
            self.selected_files = []
            indexes = self.tree.selectedIndexes()
            for index in indexes:
                item = self.model.itemFromIndex(index)
                data = item.data()
                if data['type'] == 'folder':
                    self.selected_files = []
                    self.update_model(index)
                    self.tree.expand(index)
                    return
                else:
                    self.selected_files.append(data['id'])

        super(GDriveDialog, self).done(result)

        
class SettingsDialog(QDialog, Ui_SettingsDialog):

    def __init__(self, parent, config):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)

        self.config = config

        for p in self.config.converterConfig.profiles:
            self.comboProfile.addItem('{0} ({1})'.format(p, self.config.converterConfig.profiles[p]['description']), p)

        for f in ['mobi', 'azw3', 'epub']:
            self.comboFormat.addItem(f, f)

        self.comboProfile.setCurrentIndex(self.comboProfile.findData(self.config.currentProfile))
        self.comboFormat.setCurrentIndex(self.comboFormat.findData(self.config.currentFormat))
        self.lineDestFolder.setText(self.config.outputFolder)
        self.checkWriteLog.setChecked(self.config.writeLog)
        self.checkClearLogAfterExit.setChecked(self.config.clearLogAfterExit)
        self.lineKindleDocsSubfolder.setText(self.config.kindleDocsSubfolder)
        self.lineGoogleMail.setText(self.config.GoogleMail)
        self.lineGooglePassword.setText(self.config.GooglePassword)
        self.lineKindleMail.setText(self.config.KindleMail)

        if self.config.hyphens.lower() == 'yes':
            self.radioHypYes.setChecked(True)
            self.radioHypNo.setChecked(False)
            self.radioHypProfile.setChecked(False)

        elif self.config.hyphens.lower() == 'no':
            self.radioHypYes.setChecked(False)
            self.radioHypNo.setChecked(True)
            self.radioHypProfile.setChecked(False)

        elif self.config.hyphens.lower() == 'profile':
            self.radioHypYes.setChecked(False)
            self.radioHypNo.setChecked(False)
            self.radioHypProfile.setChecked(True)

        # Строим выбор шрифта
        # для начала обновим список доступных шрифтов
        self.config.fontDb.update_db()
        self.comboFont.addItem(_translate('fb2mobi-gui', 'None'), 'None')
        for font in self.config.fontDb.families:
            self.comboFont.addItem(font, font)

        if self.config.embedFontFamily is None:
            self.comboFont.setCurrentIndex(self.comboFont.findData('None'))
        else:
            self.comboFont.setCurrentIndex(self.comboFont.findData(self.config.embedFontFamily))

        self.comboLogLevel.setCurrentIndex(self.comboLogLevel.findText(self.config.logLevel))

        self.lineKindlePath.setText(self.config.kindlePath)
        self.checkSyncCovers.setChecked(self.config.kindleSyncCovers)

    def OpenFontsFolder(self):
        fonts_folder = os.path.join(os.path.dirname(self.config.config_file), 'profiles', 'fonts')
        if not os.path.isdir(fonts_folder):
            os.makedirs(fonts_folder)

        if sys.platform == 'win32':
            os.startfile(fonts_folder)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', fonts_folder])
        else:
            try:
                subprocess.Popen(['xdg-open', fonts_folder])
            except:
                pass

    def selectDestPath(self):
        self.lineDestFolder.setText(self.selectPath(self.lineDestFolder.text()))

    def selectKindlePath(self):
        self.lineKindlePath.setText(self.selectPath(self.lineKindlePath.text()))

    def selectPath(self, path):
        if not path:
            path = os.path.expanduser('~')

        dlgPath = QFileDialog(self, _translate('fb2mobi-gui', 'Select folder'), path)
        dlgPath.setFileMode(QFileDialog.Directory)
        dlgPath.setOption(QFileDialog.ShowDirsOnly, True)

        if dlgPath.exec_():
            for d in dlgPath.selectedFiles():
                path = os.path.normpath(d)

        return path

    def closeAccept(self):
        self.config.currentProfile = self.comboProfile.currentData()
        self.config.currentFormat = self.comboFormat.currentData()
        if self.radioHypYes.isChecked():
            self.config.hyphens = 'Yes'
        elif self.radioHypNo.isChecked():
            self.config.hyphens = 'No'
        else:
            self.config.hyphens = 'Profile'

        self.config.kindlePath = os.path.normpath(self.lineKindlePath.text()) if self.lineKindlePath.text() else ''
        self.config.kindleDocsSubfolder = self.lineKindleDocsSubfolder.text()
        self.config.outputFolder = self.lineDestFolder.text()
        self.config.GoogleMail = self.lineGoogleMail.text()
        self.config.GooglePassword = self.lineGooglePassword.text()
        self.config.KindleMail = self.lineKindleMail.text()

        self.config.kindleSyncCovers = self.checkSyncCovers.isChecked()
        self.config.writeLog = self.checkWriteLog.isChecked()
        self.config.clearLogAfterExit = self.checkClearLogAfterExit.isChecked()
        self.config.logLevel = self.comboLogLevel.currentText()

        if self.comboFont.currentData() == 'None':
            self.config.embedFontFamily = None
        else:
            self.config.embedFontFamily = self.comboFont.currentData()


class AboutDialog(QDialog, Ui_AboutDialog):

    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent)
        self.setupUi(self)

        image = QPixmap(':/Images/icon128.png')
        self.labelImage.setPixmap(image)
        self.labelVersion.setText(version.VERSION)
        self.labelUIVersion.setText(ui.ui_version.VERSION)

        self.setFixedSize(self.size())


class MainAppWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super(MainAppWindow, self).__init__()
        self.setupUi(self)

        self.kindle_path = ''

        self.savedPath = ''
        self.convertRun = False
        self.convertedCount = 0
        self.copyCount = 0
        self.convertedFiles = []

        # self.setAcceptDrops(True)
        self.treeFileList.setAcceptDrops(True)
        self.treeFileList.installEventFilter(self)

        self.imgBookCover.setAcceptDrops(True)
        self.imgBookCover.installEventFilter(self)

        self.book_cover = None

        self.config_file = None
        self.log_file = None
        self.log = None
        self.config = {}

        self.convert_worker = None
        self.copy_worker = None
        self.is_convert_cancel = False

        self.rootFileList = self.treeFileList.invisibleRootItem()
        self.iconWhite = QIcon(':/Images/bullet_white.png')
        self.iconRed = QIcon(':/Images/bullet_red.png')
        self.iconGreen = QIcon(':/Images/bullet_green.png')
        self.iconGo = QIcon(':/Images/bullet_go.png')

        self.pixmapConnected = QPixmap(':/Images/bullet_green.png')
        self.pixmapNotConnected = QPixmap(':/Images/bullet_red.png')

        config_file_name = "fb2mobi.config"
        log_file_name = "fb2mobi.log"
        gui_config_file = 'fb2mobi-gui.config'

        # Определяем, где находится файл конфигурации.
        # Если есть в домашнем каталоге пользователя (для windows ~/f2bmobi, для остальных ~/.fb2mobi),
        # то используется он.
        # Иначе - из каталога программы
        application_path = os.path.normpath(fb2mobi.get_executable_path())
        config_path = None
        if sys.platform == 'win32':
            config_path = os.path.normpath(os.path.join(os.path.expanduser('~'), 'fb2mobi'))
        else:
            config_path = os.path.normpath(os.path.join(os.path.expanduser('~'), '.fb2mobi'))

        if not os.path.exists(os.path.join(config_path, config_file_name)):
            config_path = application_path

        self.config_file = os.path.normpath(os.path.join(config_path, config_file_name))
        self.log_file = os.path.normpath(os.path.join(config_path, log_file_name))
        self.gui_config_file = os.path.normpath(os.path.join(config_path, gui_config_file))
        self.credential_file = os.path.normpath(os.path.join(config_path, '.credentials', 'fb2moby-credential.json'))
        self.gdrive_temp_dir = None

        self.gui_config = GuiConfig(self.gui_config_file)
        self.gui_config.converterConfig = ConverterConfig(self.config_file)

        self.log = logging.getLogger('fb2mobi')
        self.log.setLevel(self.gui_config.logLevel)

        self.log_stream_handler = logging.StreamHandler()
        self.log_stream_handler.setLevel(fb2mobi.get_log_level(self.gui_config.converterConfig.console_level))
        self.log_stream_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        self.log.addHandler(self.log_stream_handler)

        self.log_file_handler = logging.FileHandler(filename=self.log_file, mode='a', encoding='utf-8')
        self.log_file_handler.setLevel(fb2mobi.get_log_level(self.gui_config.converterConfig.log_level))
        self.log_file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
        if self.gui_config.writeLog:
            self.log.addHandler(self.log_file_handler)

        self.gui_config.converterConfig.log = self.log
        # Строим базу доступных шрифтов
        self.font_path = os.path.normpath(os.path.join(config_path, 'profiles/fonts'))
        if os.path.exists(self.font_path):
            self.gui_config.fontDb = FontDb(self.font_path)

        if not self.gui_config.lastUsedTargetPath:
            self.gui_config.lastUsedTargetPath = os.path.abspath(os.path.expanduser("~/Desktop"))

        if not self.gui_config.currentFormat:
            self.gui_config.currentFormat = 'mobi'

        if not self.gui_config.currentProfile:
            for p in self.gui_config.converterConfig.profiles:
                self.gui_config.currentProfile = p
                break

        if not self.gui_config.hyphens:
            self.gui_config.hyphens = 'profile'

        if self.gui_config.geometry['x'] and self.gui_config.geometry['y']:
            self.move(self.gui_config.geometry['x'], self.gui_config.geometry['y'])
            self.resize(self.gui_config.geometry['width'], self.gui_config.geometry['height'])

        self.setWindowIcon(QIcon(':/Images/icon32.png'))
        self.treeFileList.installEventFilter(self)
        self.bookInfoSplitter.installEventFilter(self)

        self.labelStatus = QLabel()

        self.imgBookCover.setContextMenuPolicy(Qt.CustomContextMenu)
        self.imgBookCover.customContextMenuRequested[QPoint].connect(self.contextCoverMenu)

        self.toolBar.setIconSize(QSize(24, 24))

        self.toolAdd.setIcon(QIcon(':/toolbar/add.png'))
        self.toolSaveToDisk.setIcon(QIcon(':/toolbar/save.png'))
        self.toolSendToKindle.setIcon(QIcon(':/toolbar/kindle.png'))
        self.toolSendToKindle.setEnabled(False)
        self.toolSendMail.setIcon(QIcon(':/toolbar/send.png'))
        self.toolSettings.setIcon(QIcon(':/toolbar/settings.png'))
        self.toolInfo.setIcon(QIcon(':/toolbar/info_on.png'))
        self.actionAddGDirve.setIcon(QIcon(':/toolbar/gdrive.png'))
        self.actionRename.setIcon(QIcon(':/toolbar/rename.png'))

        # Немного подстраиваем стили UI для более нативного отображения
        if sys.platform == 'darwin':
            # Для Mac OS X
            font = self.labelStatus.font()
            font.setPointSize(11)
            self.labelStatus.setFont(font)
            self.treeFileList.setFont(font)
            self.labelAuthor.setFont(font)
            self.labelBookTitle.setFont(font)
            self.labelSeries.setFont(font)
            self.labelSeriesNumber.setFont(font)
            self.labelBookLanguage.setFont(font)
            self.treeFileList.setAttribute(Qt.WA_MacShowFocusRect, 0)
            self.treeFileList.setStyleSheet(TREE_LIST_CSS_ACTIVE)
            self.labelStatus.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

            self.toolBar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            self.setUnifiedTitleAndToolBarOnMac(True)
            self.toolBar.addAction(self.toolAdd)
            self.toolBar.addAction(self.actionAddGDirve)
            # spacer = QWidget()
            # spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # self.toolBar.addWidget(spacer)
            self.toolBar.addAction(self.toolSaveToDisk)
            self.toolBar.addAction(self.toolSendToKindle)
            self.toolBar.addAction(self.toolSendMail)
            self.toolBar.addAction(self.actionRename)
            # spacer = QWidget()
            # spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # self.toolBar.addWidget(spacer)
            # self.toolBar.addAction(self.actionRename)
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.toolBar.addWidget(spacer)            
            self.toolBar.addAction(self.toolInfo)
            self.toolBar.addAction(self.toolSettings)
        else:
            # Для Windows, Linux
            self.toolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self.toolBar.setStyleSheet('QToolButton { padding: 2px; }')

            spacer = QWidget()

            self.toolBar.addAction(self.toolAdd)
            self.toolBar.addAction(self.actionAddGDirve)
            self.toolBar.addSeparator()
            self.toolBar.addAction(self.toolSaveToDisk)
            self.toolBar.addAction(self.toolSendToKindle)
            self.toolBar.addAction(self.toolSendMail)
            self.toolBar.addSeparator()
            self.toolBar.addAction(self.actionRename)
            self.toolBar.addAction(self.toolSettings)
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.toolBar.addWidget(spacer)
            self.toolBar.addAction(self.toolInfo)
            self.toolInfo.setPriority(QAction.LowPriority)

            self.toolAdd.setPriority(QAction.LowPriority)
            self.actionAddGDirve.setPriority(QAction.LowPriority)
            self.toolSaveToDisk.setPriority(QAction.LowPriority)
            self.toolSendToKindle.setPriority(QAction.LowPriority)
            self.toolSendMail.setPriority(QAction.LowPriority)
            self.actionRename.setPriority(QAction.LowPriority)
            self.toolSettings.setPriority(QAction.LowPriority)

        self.setBookInfoPanelVisible()
        self.scrollBookInfo.setVisible(self.gui_config.bookInfoVisible)
        if self.gui_config.bookInfoSplitterState:
            splitter_sizes = self.gui_config.bookInfoSplitterState.split(',')
            self.bookInfoSplitter.setSizes([int(i) for i in splitter_sizes])

        self.statusBar().addWidget(self.labelStatus, 1)

        for col in self.gui_config.columns.keys():
            self.treeFileList.setColumnWidth(int(col), self.gui_config.columns[col])

        self.timerKindleStatus = QTimer()
        self.timerKindleStatus.timeout.connect(self.checkKindleStatus)
        self.timerKindleStatus.start(1500)

        self.enableSendViaMail()

        self.comboGenres.addItem(_translate('fb2mobi-gui', '<Empty>'))
        self.comboGenres.setItemData(0, 'empty')

        for genre in ui.genres.genres:
            self.comboGenres.addItem('{0} ({1})'.format(ui.genres.genres[genre], genre))
            self.comboGenres.setItemData(self.comboGenres.count() - 1, genre)

    def event(self, event):
        if event.type() == QEvent.WindowActivate:
            if sys.platform == 'darwin':
                self.treeFileList.setStyleSheet(TREE_LIST_CSS_ACTIVE)
        elif event.type() == QEvent.WindowDeactivate:
            if sys.platform == 'darwin':
                self.treeFileList.setStyleSheet(TREE_LIST_CSS_UNACTIVE)

        return super(MainAppWindow, self).event(event)

    def getFileList(self):
        files = []
        for i in range(self.rootFileList.childCount()):
            files.append(self.rootFileList.child(i).text(4))

        return files

    def process(self, mode):
        files = self.getFileList()
        dest_files = []

        self.gui_config.converterConfig = ConverterConfig(self.config_file)
        self.gui_config.converterConfig.log = self.log

        if self.gui_config.embedFontFamily:
            self.generateFontCSS()

        config = self.gui_config.converterConfig

        if len(files) > 0:
            progressDlg = QProgressDialog(self)
            progressDlg.setWindowModality(Qt.WindowModal)
            progressDlg.setMinimumDuration(0)
            progressDlg.setLabelText(_translate('fb2mobi-gui', 'Converting...'))
            progressDlg.setRange(0, len(files))
            progressDlg.setAutoClose(False)
            progressDlg.forceShow()

            # Подготовка профиля конвертера
            config.setCurrentProfile(self.gui_config.currentProfile)
            config.output_format = self.gui_config.currentFormat
            # Отключим отправку книг на Kinlde из командной строки
            config.send_to_kindle['send'] = False
            if self.gui_config.embedFontFamily:
                css_file = os.path.join(os.path.dirname(self.gui_config.config_file), 'profiles', '_font.css')
                if os.path.exists(css_file):
                    config.current_profile['css'] = css_file

            if mode == PROCESS_MODE_CONVERT:
                config.output_dir = self.gui_config.outputFolder if self.gui_config.outputFolder else self.gui_config.lastUsedTargetPath
            else:
                config.output_dir = tempfile.mkdtemp()

            if self.gui_config.hyphens.lower() == 'yes':
                config.current_profile['hyphens'] = True
            elif self.gui_config.hyphens.lower() == 'no':
                config.current_profile['hyphens'] = False

            i = 0
            errors = 0

            for file in files:
                result = True
                i += 1
                progressDlg.setValue(i)

                output_dir = os.path.abspath(config.output_dir)
                file_name = os.path.join(output_dir, os.path.splitext(os.path.split(file)[1])[0])
                if os.path.splitext(file_name)[1].lower() == '.fb2':
                    file_name = os.path.splitext(file_name)[0]

                dest_file = '{0}.{1}'.format(file_name, config.output_format)
                # Перед конвертацией попробуем удалить старый файл - если в профиле есть <outputPattern> - это не сработает
                if os.path.exists(dest_file):
                    os.remove(dest_file)

                config.log.info(' ')
                # on success process_file will return proper new destination name
                dest_file = fb2mobi.process_file(config, file, None)
                self.log.debug('Resulting file: "{0}"'.format(dest_file))

                # Отметим результат конвертации
                item = None
                for j in range(self.rootFileList.childCount()):
                    if file == self.rootFileList.child(j).text(4):
                        item = self.rootFileList.child(j)
                        if dest_file and os.path.exists(dest_file):
                            dest_files.append(dest_file)
                            item.setIcon(0, self.iconGreen)
                        else:
                            item.setIcon(0, self.iconRed)
                            errors += 1

                if progressDlg.wasCanceled():
                    break
               

            if errors > 0:
                QMessageBox.warning(self, _translate('fb2mobi-gui', 'Error'), _translate('fb2mobi-gui', 'Error while converting file(s). Check log for details.'))

            if mode == PROCESS_MODE_KINDLE:
                kindle_doc_path = os.path.join(self.kindle_path, 'documents')
                if self.gui_config.kindleDocsSubfolder:
                    kindle_doc_path = os.path.join(kindle_doc_path, self.gui_config.kindleDocsSubfolder)
                    if not os.path.isdir(kindle_doc_path):
                        try:
                            os.makedirs(kindle_doc_path)
                        except:
                            self.log.critical('Error while creating subfolder {0} in documents folder.'.format(self.gui_config.kindleDocsSubfolder))
                            self.log.debug('Getting details', exc_info=True)
                            QMessageBox.critical(self, _translate('fb2mobi-gui', 'Error'), _translate('fb2mobi-gui', 'Error while sending file(s). Check log for details.'))
                            return

                thumbnail_path = os.path.join(self.kindle_path, 'system', 'thumbnails')
                if not os.path.isdir(thumbnail_path):
                    thumbnail_path = ''

                if os.path.exists(kindle_doc_path):
                    progressDlg.setLabelText(_translate('fb2mobi-gui', 'Sending to Kindle...'))
                    progressDlg.setRange(0, len(dest_files))
                    i = 0
                    errors = 0
                    for file in dest_files:
                        i += 1
                        progressDlg.setValue(i)
                        try:
                            shutil.copy2(file, kindle_doc_path)
                            src_sdr_dir = '{0}.{1}'.format(os.path.splitext(file)[0], 'sdr')
                            dest_sdr_dir = os.path.join(kindle_doc_path, os.path.split(src_sdr_dir)[1])
                            if os.path.isdir(src_sdr_dir):
                                if os.path.isdir(dest_sdr_dir):
                                    shutil.rmtree(dest_sdr_dir)
                                shutil.copytree(src_sdr_dir, dest_sdr_dir)

                            # Создадим миниатюру обложки, если оперделили путь и установлен признак
                            if thumbnail_path and self.gui_config.kindleSyncCovers:
                                dest_file = os.path.join(kindle_doc_path, os.path.split(file)[1])
                                if os.path.exists(dest_file):
                                    synccovers.process_file(dest_file, thumbnail_path, 330, 470, False, False)
                        except:
                            self.log.critical('Error while sending file {0}.'.format(file))
                            self.log.debug('Getting details', exc_info=True)
                            errors += 1

                        if progressDlg.wasCanceled() or errors == 3:
                            break

                if errors > 0:
                    QMessageBox.critical(self, _translate('fb2mobi-gui', 'Error'), _translate('fb2mobi-gui', 'Error while sending file(s). Check log for details.'))

                fb2mobi.rm_tmp_files(config.output_dir, True)

            if mode == PROCESS_MODE_MAIL:
                progressDlg.setLabelText(_translate('fb2mobi-gui', 'Sending via Gmail...'))
                progressDlg.setRange(0, len(dest_files))

                kindle = SendToKindle()
                kindle.smtp_server = 'smtp.gmail.com'
                kindle.smtp_port = '587'
                kindle.smtp_login = self.gui_config.GoogleMail
                kindle.smtp_password = self.gui_config.GooglePassword
                kindle.user_email = self.gui_config.GoogleMail
                kindle.kindle_email = self.gui_config.KindleMail
                kindle.convert = False

                i = 0
                errors = 0
                for file in dest_files:
                    i += 1
                    progressDlg.setValue(i)
                    try:
                        kindle.send_mail([file])
                    except:
                        self.log.critical('Error while sending file {0}.'.format(file))
                        self.log.debug('Getting details', exc_info=True)
                        errors += 1

                    if progressDlg.wasCanceled() or errors == 3:
                        break

                if errors > 0:
                    QMessageBox.critical(self, _translate('fb2mobi-gui', 'Error'), _translate('fb2mobi-gui', 'Error while sending file(s). Check log for details.'))

                fb2mobi.rm_tmp_files(config.output_dir, True)

            progressDlg.deleteLater()

    def convertToDisk(self):
        files = self.getFileList()
        if len(files) > 0:
            if not self.gui_config.outputFolder:
                dlgPath = QFileDialog(self, _translate('fb2mobi-gui', 'Select folder to convert'), self.gui_config.lastUsedTargetPath)
                dlgPath.setFileMode(QFileDialog.Directory)
                dlgPath.setOption(QFileDialog.ShowDirsOnly, True)

                if dlgPath.exec_():
                    for d in dlgPath.selectedFiles():
                        self.gui_config.lastUsedTargetPath = os.path.normpath(d)
                    self.process(PROCESS_MODE_CONVERT)
            else:
                self.process(PROCESS_MODE_CONVERT)

    def sendToKindle(self):
        self.process(PROCESS_MODE_KINDLE)

    def sendViaMail(self):
        self.process(PROCESS_MODE_MAIL)

    def enableSendViaMail(self):
        if self.gui_config.GoogleMail and self.gui_config.GooglePassword and self.gui_config.KindleMail and self.gui_config.currentFormat.lower() == 'mobi':
            self.toolSendMail.setEnabled(True)
            self.actionSendViaMail.setEnabled(True)
        else:
            self.toolSendMail.setEnabled(False)
            self.actionSendViaMail.setEnabled(False)

    def findKindle(self):
        mounted_fs = []
        add_files = []

        if sys.platform == 'darwin':
            list_dir = os.listdir('/Volumes')
            for dir_name in list_dir:
                mounted_fs.append(os.path.join('/Volumes', dir_name))
        else:
            import psutil
            mounted_list = psutil.disk_partitions()
            for fs in mounted_list:
                if fs.fstype:
                    mounted_fs.append(fs.mountpoint)

        for fs in mounted_fs:
            dir_documents = os.path.join(fs, 'documents')
            dir_system = os.path.join(fs, 'system')

            if os.path.exists(dir_documents) and os.path.exists(dir_system):
                # Kindle Paperwhite, Voyage, Oasis
                if os.path.exists(os.path.join(fs, 'system', 'thumbnails')) and os.path.exists(os.path.join(fs, 'system', 'version.txt')):
                    return fs
                # Kindle 4, 5
                elif os.path.exists(os.path.join(fs, 'system', 'com.amazon.ebook.booklet.reader', 'reader.pref')):
                    return fs

        return ''

    def checkKindleStatus(self):
        if self.gui_config.kindlePath:
            self.kindle_path = self.gui_config.kindlePath
        else:
            self.kindle_path = self.findKindle()

        if self.kindle_path and os.path.isdir(self.kindle_path):
            self.toolSendToKindle.setEnabled(True)
            self.actionSendToKindle.setEnabled(True)
            self.labelStatus.setText(_translate('fb2mobi-gui', 'Kindle connected to {0}').format(self.kindle_path))
        else:
            self.toolSendToKindle.setEnabled(False)
            self.actionSendToKindle.setEnabled(False)
            self.labelStatus.setText('')

    def setBookInfoPanelVisible(self):
        if self.gui_config.bookInfoVisible:
            self.toolInfo.setIcon(QIcon(':/toolbar/info_on.png'))
        else:
            self.toolInfo.setIcon(QIcon(':/toolbar/info_off.png'))

        self.scrollBookInfo.setVisible(self.gui_config.bookInfoVisible)

    def switchInfoPanel(self):
        self.gui_config.bookInfoVisible = not self.gui_config.bookInfoVisible
        self.setBookInfoPanelVisible()

    def eventFilter(self, source, event):
        if source is self.treeFileList:
            if event.type() == QEvent.DragEnter:
                if event.mimeData().hasUrls():
                    event.accept()
                    return True
                else:
                    event.ignore()

            elif event.type() == QEvent.Drop:
                file_list = [u.toLocalFile() for u in event.mimeData().urls()]
                self.addFiles(file_list)
                event.accept()
                return True

        elif source is self.imgBookCover:
            if event.type() == QEvent.DragEnter:
                if event.mimeData().hasUrls():
                    if len(self.treeFileList.selectedItems()) == 1:
                        event.accept()
                        return True
                    else:
                        event.ignore()
                else:
                    event.ignore()

            elif event.type() == QEvent.Drop:
                file_list = [u.toLocalFile() for u in event.mimeData().urls()]
                for f in file_list:
                    self.loadNewCoverFormFile(f)
                    break
                event.accept()
                return True

        elif source is self.bookInfoSplitter:
            if event.type() == QEvent.Paint:
                splitter_sizes = self.bookInfoSplitter.sizes()
                if splitter_sizes[1] > 0:
                    self.gui_config.bookInfoSplitterState = ', '.join(str(e) for e in splitter_sizes)

        if event.type() == QEvent.KeyPress:
            if (event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace and event.modifiers() == Qt.ControlModifier)):
                self.deleteRecAction()
                return True

        return QWidget.eventFilter(self, source, event)

    def contextCoverMenu(self, point):
        if len(self.treeFileList.selectedItems()) == 1:
            menu = QMenu()

            actionLoad = menu.addAction(_translate('fb2mobi-gui', 'Load from file...'))
            actionSave = menu.addAction(_translate('fb2mobi-gui', 'Save to file...'))
            actionClear = menu.addAction(_translate('fb2mobi-gui', 'Clear'))

            action = menu.exec_(self.imgBookCover.mapToGlobal(point))

            if action == actionLoad:
                fileDialog = QFileDialog(self, _translate('fb2mobi-gui', 'Select book cover'))
                fileDialog.setFileMode(QFileDialog.ExistingFile)
                fileDialog.setNameFilters([_translate('fb2mobi-gui', 'Image files (*.png *.jpg *.bmp)')])

                if fileDialog.exec_():
                    file_list = fileDialog.selectedFiles()
                    self.loadNewCoverFormFile(file_list[0])
            elif action == actionSave:
                fileDialog = QFileDialog(self, _translate('fb2mobi-gui', 'Save cover as'))
                fileDialog.setAcceptMode(QFileDialog.AcceptSave)
                fileDialog.setFileMode(QFileDialog.AnyFile)
                fileDialog.setNameFilters([_translate('fb2mobi-gui', 'Image files (*.png *.jpg *.bmp)')])

                if fileDialog.exec_():
                    file_list = fileDialog.selectedFiles()
                    self.book_cover.save(file_list[0],
                                         os.path.splitext(file_list[0])[1][1:].upper())

            elif action == actionClear:
                self.book_cover = None
                self.imgBookCover.clear()

    def selectAllAction(self):
        self.treeFileList.selectAll()

    def deleteRecAction(self):
        for item in self.treeFileList.selectedItems():
            self.rootFileList.removeChild(item)

    def deleteAllAction(self):
        if self.treeFileList.topLevelItemCount() > 0:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle(_translate('fb2mobi', 'Delete from list'))
            msg.setText(_translate('fb2mobi', 'Delete all files from list?'))
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            if msg.exec_() == QMessageBox.Yes:
                self.treeFileList.clear()

    def openLog(self):
        self.openFile(self.log_file)

    def generateFontCSS(self):
        # Список стилей для встраивания шрифтов
        style_rules = ['.titleblock', '.text-author', 'p', 'p.title', '.cite', '.poem', '.table th', '.table td', '.annotation', 'body']

        css_string = modules.default_css.gui_default_css
        css = cssutils.parseString(css_string)

        font_regular = ''
        font_italic = ''
        font_bold = ''
        font_bolditalic = ''

        if 'Regular' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_regular = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Regular']

        if 'Italic' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_italic = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Italic']
        else:
            font_italic = font_regular

        if 'Bold' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_bold = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Bold']
        else:
            font_bold = font_regular

        if 'Bold Italic' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_bolditalic = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Bold Italic']
        else:
            font_bolditalic = font_italic

        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); }}'.format(font_regular))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-style: italic; }}'.format(font_italic))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-weight: bold; }}'.format(font_bold))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-style: italic; font-weight: bold; }}'.format(font_bolditalic))

        found_body = False

        for rule in css:
            if rule.type == rule.STYLE_RULE:
                if rule.selectorText in style_rules:
                    rule.style['font-family'] = '"para"'
                if rule.selectorText == 'body':
                    found_body = True

        # Добавим стиль для
        if not found_body:
            css.add('body {font-family: "para"; line-height: 100%; }')

        css_path = os.path.join(os.path.dirname(self.config_file), 'profiles')
        if not os.path.exists(css_path):
            os.makedirs(css_path)

        with codecs.open(os.path.join(css_path, '_font.css'), 'w', 'utf-8') as f:
            f.write(str(css.cssText, 'utf-8'))

    def loadNewCoverFormFile(self, img_file):
        self.book_cover = QPixmap(img_file)
        self.displayCoverThumbmail(self.book_cover)

    def clearBookInfo(self):
        self.book_cover = None
        self.imgBookCover.clear()
        self.editAuthor.clear()
        self.editTitle.clear()
        self.editSeries.clear()
        self.comboGenres.setCurrentIndex(0)
        self.editSeriesNumber.clear()
        self.editBookLanguage.clear()
        self.editTranslator.clear()

    def saveBookInfo(self):
        selected_items = self.treeFileList.selectedItems()
        if len(selected_items) == 1:
            QApplication.setOverrideCursor(Qt.BusyCursor)

            item = selected_items[0]
            meta = EbookMeta(item.text(4))
            meta.get()

            if self.book_cover:
                data = QByteArray()
                buf = QBuffer(data)
                self.book_cover.save(buf, 'JPG')
                meta.coverdata = bytes(buf.buffer())
                if not meta.coverpage:
                    meta.coverpage = 'cover.jpg'
                    meta.coverpage_href = '{http://www.w3.org/1999/xlink}href'
            else:
                meta.coverpage = ''
                meta.coverdata = None

            meta.set_authors(self.editAuthor.text())
            meta.book_title = self.editTitle.text()
            meta.set_series(self.editSeries.text(), self.editSeriesNumber.text())
            meta.lang = self.editBookLanguage.text()
            meta.set_genre(self.comboGenres.itemData(self.comboGenres.currentIndex()))
            meta.set_translators(self.editTranslator.text())
            meta.write()

            item.setText(0, meta.book_title)
            item.setText(1, meta.get_autors())
            item.setText(2, meta.get_first_series_str())
            item.setText(3, meta.get_first_genre_name())

            item.setToolTip(0, meta.book_title)
            item.setToolTip(1, meta.get_autors())
            item.setToolTip(2, meta.get_first_series_str())
            item.setToolTip(3, meta.get_first_genre_name())

            QApplication.restoreOverrideCursor()
        elif len(selected_items) > 1:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle(_translate('fb2mobi', 'Save'))
            msg.setText(_translate('fb2mobi', 'Save changes in selected files?'))
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
            if msg.exec_() == QMessageBox.Save:
                QApplication.setOverrideCursor(Qt.BusyCursor)

                for item in selected_items:
                    meta = EbookMeta(item.text(4))
                    meta.get()
                    (series_name, series_num) = meta.get_first_series()

                    if self.editAuthor.text():
                        meta.set_authors(self.editAuthor.text())
                    if self.editSeries.text():
                        series_name = self.editSeries.text()
                        meta.set_series(series_name, series_num)
                    if self.editTranslator.text():
                        meta.set_translators(self.editTranslator.text())
                    if self.editBookLanguage.text():
                        meta.lang = self.editBookLanguage.text()
                    if self.comboGenres.currentIndex() > 0:
                        meta.set_genre(self.comboGenres.itemData(self.comboGenres.currentIndex()))
                    meta.write()

                    item.setText(0, meta.book_title)
                    item.setText(1, meta.get_autors())
                    item.setText(2, meta.get_first_series_str())
                    item.setText(3, meta.get_first_genre_name())

                    item.setToolTip(0, meta.book_title)
                    item.setToolTip(1, meta.get_autors())
                    item.setToolTip(2, meta.get_first_series_str())
                    item.setToolTip(3, meta.get_first_genre_name())

                QApplication.restoreOverrideCursor()

    def displayCoverThumbmail(self, img):
        scaled_img = img.scaled(120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter = QPainter(scaled_img)
        painter.setBackgroundMode(Qt.OpaqueMode)
        cur_font = painter.font()
        cur_font.setWeight(QFont.Bold)
        painter.setFont(cur_font)
        img_size = '{0}x{1}'.format(img.width(), img.height())
        metrics = QFontMetrics(cur_font)
        painter.drawText(2, metrics.boundingRect(img_size).height(), img_size)
        painter.end()

        self.imgBookCover.setPixmap(scaled_img)

    def changeBook(self):
        self.clearBookInfo()

        selected_items = self.treeFileList.selectedItems()
        if len(selected_items) == 1:
            self.editTitle.setEnabled(True)
            self.editSeriesNumber.setEnabled(True)

            meta = EbookMeta(selected_items[0].text(4))
            meta.get()

            self.editAuthor.setText(meta.get_autors())
            self.editTitle.setText(meta.book_title)
            (series_name, series_num) = meta.get_first_series()
            self.editSeries.setText(series_name)
            self.editSeriesNumber.setText(series_num)
            self.editBookLanguage.setText(meta.lang)
            self.editTranslator.setText(meta.get_translators())

            found_genre = False
            if meta.genre:
                for i in range(self.comboGenres.count()):
                    data = self.comboGenres.itemData(i)
                    if data == meta.get_first_genre():
                        self.comboGenres.setCurrentIndex(i)
                        found_genre = True
                        break
                if not found_genre:
                    self.comboGenres.setCurrentIndex(0)    
            else:
                self.comboGenres.setCurrentIndex(0)

            if meta.coverdata:
                self.book_cover = QPixmap()
                self.book_cover.loadFromData(meta.coverdata)
                self.displayCoverThumbmail(self.book_cover)

            if meta.book_type == 'fb2':
                self.editAuthor.setEnabled(True)
                self.editTitle.setEnabled(True)
                self.editSeries.setEnabled(True)
                self.editSeriesNumber.setEnabled(True)
                self.comboGenres.setEnabled(True)
                self.editBookLanguage.setEnabled(True)
                self.editTranslator.setEnabled(True)
                self.buttonSaveBookInfo.setEnabled(True)
            else:
                self.editAuthor.setEnabled(False)
                self.editTitle.setEnabled(False)
                self.editSeries.setEnabled(False)
                self.editSeriesNumber.setEnabled(False)
                self.comboGenres.setEnabled(False)
                self.editBookLanguage.setEnabled(False)
                self.editTranslator.setEnabled(False)
                self.buttonSaveBookInfo.setEnabled(False)

        elif len(selected_items) > 1:
            self.editAuthor.setEnabled(True)
            self.editTitle.setEnabled(False)
            self.editSeries.setEnabled(True)
            self.editSeriesNumber.setEnabled(False)
            self.comboGenres.setEnabled(True)
            self.editBookLanguage.setEnabled(True)
            self.editTranslator.setEnabled(True)
            self.buttonSaveBookInfo.setEnabled(True)

    def addFile(self, file):
        if not file.lower().endswith(('.fb2', '.fb2.zip', '.zip', '.epub')):
            return

        found = False

        file = os.path.normpath(file)

        for i in range(self.rootFileList.childCount()):
            if file == self.rootFileList.child(i).text(2):
                found = True
                break

        if not found:
            meta = EbookMeta(file)
            meta.get()

            item = QTreeWidgetItem(0)
            item.setIcon(0, self.iconWhite)
            item.setText(0, meta.book_title)
            item.setText(1, meta.get_autors())
            item.setText(2, meta.get_first_series_str())
            item.setText(3, meta.get_first_genre_name())
            item.setText(4, file)
            # Установим подсказки
            item.setToolTip(0, meta.book_title)
            item.setToolTip(1, meta.get_autors())
            item.setToolTip(2, meta.get_first_series_str())
            item.setToolTip(3, meta.get_first_genre_name())
            item.setToolTip(4, file)

            self.treeFileList.addTopLevelItem(item)

    def addFiles(self, file_list):
        QApplication.setOverrideCursor(Qt.BusyCursor)
        for item in file_list:
            if os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for f in files:
                        self.addFile(os.path.join(root, f))
            else:
                self.addFile(item)
        QApplication.restoreOverrideCursor()

    def addFilesAction(self):
        if not self.gui_config.lastUsedPath:
            self.gui_config.lastUsedPath = os.path.expanduser('~')

        fileDialog = QFileDialog(self, _translate('fb2mobi-gui', 'Select files'), self.gui_config.lastUsedPath)
        fileDialog.setFileMode(QFileDialog.ExistingFiles)
        fileDialog.setNameFilters([_translate('fb2mobi-gui', 'Ebook files (*.fb2 *.fb2.zip *.zip *.epub)'), _translate('fb2mobi-gui', 'All files (*.*)')])

        if fileDialog.exec_():
            self.gui_config.lastUsedPath = os.path.normpath(fileDialog.directory().absolutePath())
            file_list = fileDialog.selectedFiles()
            self.addFiles(file_list)

    def closeApp(self):
        # Очистим лог-файл на выходе, если указано в настройках
        if self.gui_config.clearLogAfterExit:
            if self.log_file:
                with open(self.log_file, 'w'):
                    pass

        # Если загружали файлы с Google диска, почистим
        if self.gdrive_temp_dir:
            if os.path.exists(self.gdrive_temp_dir):
                shutil.rmtree(self.gdrive_temp_dir)

        win_x = self.pos().x()
        win_y = self.pos().y()
        win_width = self.size().width()
        win_height = self.size().height()

        self.gui_config.geometry['x'] = win_x
        self.gui_config.geometry['y'] = win_y
        self.gui_config.geometry['width'] = win_width
        self.gui_config.geometry['height'] = win_height

        self.gui_config.columns['0'] = self.treeFileList.columnWidth(0)
        self.gui_config.columns['1'] = self.treeFileList.columnWidth(1)
        self.gui_config.columns['2'] = self.treeFileList.columnWidth(2)
        self.gui_config.columns['3'] = self.treeFileList.columnWidth(3)
        self.gui_config.columns['4'] = self.treeFileList.columnWidth(4)

        self.gui_config.write()

        self.close()

    def openFromGDrive(self):
        try:
            gdriveDlg = GDriveDialog(self, self.credential_file, fb2mobi.get_executable_path())
            files = []
            if gdriveDlg.exec_():
                if len(gdriveDlg.selected_files) > 0:
                    if not self.gdrive_temp_dir:
                        self.gdrive_temp_dir = tempfile.mkdtemp()
                    progressDlg = QProgressDialog(self)
                    progressDlg.setWindowModality(Qt.WindowModal)
                    progressDlg.setMinimumDuration(0)
                    progressDlg.setLabelText(_translate('fb2mobi-gui', 'Download files from Google Drive...'))
                    progressDlg.setRange(0, len(gdriveDlg.selected_files))
                    progressDlg.setAutoClose(False)
                    progressDlg.forceShow()

                    i = 0

                    for file_id in gdriveDlg.selected_files:
                        i += 1
                        progressDlg.setValue(i)

                        file_name = gdriveDlg.gdrive.download(file_id, self.gdrive_temp_dir)
                        files.append(file_name)                    
                        if progressDlg.wasCanceled():
                            break

                    progressDlg.deleteLater()
                    self.addFiles(files)
        except Exception as e:
            QMessageBox.critical(self, _translate('fb2mobi-gui', 'Error'), str(e))

    def rename(self):
        files_to_rename = []
        if len(self.treeFileList.selectedItems()) > 0:
            selected_items = self.treeFileList.selectedItems()
            for item in selected_items:
                files_to_rename.append(item.text(4))

            renDlg = RenameDialog(self, self.gui_config.authorPattern, 
                self.gui_config.filenamePattern, 
                self.gui_config.renameDestDir,
                self.gui_config.deleteAfterRename,
                files_to_rename)
            if renDlg.exec_():
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle(_translate('fb2mobi', 'Rename'))
                msg.setText(_translate('fb2mobi', 'Rename selected files?'))
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                if msg.exec_() == QMessageBox.Yes:
                    self.gui_config.authorPattern = renDlg.lineAuthorPattern.text()
                    self.gui_config.filenamePattern = renDlg.lineFilenamePattern.text()
                    if renDlg.radioRenameTo.isChecked():
                        self.gui_config.renameDestDir = renDlg.lineDestFolder.text().strip()
                    else:
                        self.gui_config.renameDestDir = None
                    self.gui_config.deleteAfterRename = renDlg.checkDeleteAfterRename.checkState()

                    selected_items = self.treeFileList.selectedItems()
                    errors = 0

                    progressDlg = QProgressDialog(self)
                    progressDlg.setWindowModality(Qt.WindowModal)
                    progressDlg.setMinimumDuration(0)
                    progressDlg.setLabelText(_translate('fb2mobi-gui', 'Renaming files...'))
                    progressDlg.setRange(0, len(selected_items))
                    progressDlg.setAutoClose(False)
                    progressDlg.forceShow()

                    i = 0
                    for item in selected_items:
                        try:
                            i += 1
                            progressDlg.setValue(i)

                            file = item.text(4)
                            meta = EbookMeta(file)
                            meta.get()
                            new_file = meta.meta_to_filename(self.gui_config.authorPattern, 
                                self.gui_config.filenamePattern,
                                dest_path=self.gui_config.renameDestDir)
                            if os.path.exists(new_file):
                                raise Exception('File {} exist!'.format(new_file))
                            else:
                                copy_file(file, new_file)
                            if self.gui_config.deleteAfterRename:
                                os.remove(file)
                            item.setText(4, new_file)
                            item.setToolTip(4, new_file)
                        except Exception as e:
                            self.log.critical('Error while renaming  file {0}: {1}.'.format(file, str(e)))
                            self.log.debug('Getting details', exc_info=True)
                            errors += 1

                    progressDlg.deleteLater()

                    if errors > 0:
                        QMessageBox.critical(self, _translate('fb2mobi-gui', 'Error'), _translate('fb2mobi-gui', 'Error while renaming file(s).\nCheck log for details.'))
                    

    def openHelpURL(self):
        webbrowser.open(url=HELP_URL)

    def openSupportURL(self):
        webbrowser.open(url=SUPPORT_URL)

    def openFile(self, filename):
        if sys.platform == 'win32':
            os.startfile(filename)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', filename])
        else:
            try:
                subprocess.Popen(['xdg-open', filename])
            except:
                pass

    def settings(self):
        prev_writeLog = self.gui_config.writeLog

        settingsDlg = SettingsDialog(self, self.gui_config)
        if settingsDlg.exec_():
            self.gui_config = settingsDlg.config
            self.gui_config.write()
            self.log.setLevel(self.gui_config.logLevel)

            if prev_writeLog != self.gui_config.writeLog:
                if self.gui_config.writeLog:
                    self.gui_config.converterConfig.log.addHandler(self.log_file_handler)
                else:
                    self.gui_config.converterConfig.log.removeHandler(self.log_file_handler)

        self.enableSendViaMail()

    def about(self):
        aboutDlg = AboutDialog(self)
        aboutDlg.exec_()

    def closeEvent(self, event):
        self.closeApp()


class AppEventFilter(QObject):
    def __init__(self, app_win):
        super(AppEventFilter, self).__init__()
        self.app_win = app_win

    def eventFilter(self, receiver, event):
        if event.type() == QEvent.FileOpen:
            self.app_win.addFiles([event.file()])
            return True
        else:
            return super(AppEventFilter, self).eventFilter(receiver, event)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    app_path = os.path.normpath(fb2mobi.get_executable_path())
    locale_path = os.path.join(app_path, 'ui/locale')
    locale = QLocale.system().name()[:2]

    qt_translator = QTranslator()
    qt_translator.load(os.path.join(locale_path, 'qtbase_' + locale + '.qm'))
    app.installTranslator(qt_translator)

    app_translator = QTranslator()
    app_translator.load(os.path.join(locale_path, 'fb2mobi_' + locale + '.qm'))
    app.installTranslator(app_translator)

    app.setStyleSheet('QStatusBar::item { border: 0px }')

    mainAppWindow = MainAppWindow()
    mainAppWindow.show()

    appEventFilter = AppEventFilter(mainAppWindow)
    app.installEventFilter(appEventFilter)

    sys.exit(app.exec_())
