# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\RenameDialog.ui'
#
# Created by: PyQt5 UI code generator 5.10.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_RenameDialog(object):
    def setupUi(self, RenameDialog):
        RenameDialog.setObjectName("RenameDialog")
        RenameDialog.resize(443, 359)
        self.gridLayout = QtWidgets.QGridLayout(RenameDialog)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(RenameDialog)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.lineAuthorPattern = QtWidgets.QLineEdit(RenameDialog)
        self.lineAuthorPattern.setObjectName("lineAuthorPattern")
        self.verticalLayout.addWidget(self.lineAuthorPattern)
        self.label_3 = QtWidgets.QLabel(RenameDialog)
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.lineFilenamePattern = QtWidgets.QLineEdit(RenameDialog)
        self.lineFilenamePattern.setObjectName("lineFilenamePattern")
        self.verticalLayout.addWidget(self.lineFilenamePattern)
        self.radioSameDir = QtWidgets.QRadioButton(RenameDialog)
        self.radioSameDir.setChecked(True)
        self.radioSameDir.setObjectName("radioSameDir")
        self.verticalLayout.addWidget(self.radioSameDir)
        self.radioRenameTo = QtWidgets.QRadioButton(RenameDialog)
        self.radioRenameTo.setObjectName("radioRenameTo")
        self.verticalLayout.addWidget(self.radioRenameTo)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineDestFolder = QtWidgets.QLineEdit(RenameDialog)
        self.lineDestFolder.setObjectName("lineDestFolder")
        self.horizontalLayout.addWidget(self.lineDestFolder)
        self.buttonSelectFolder = QtWidgets.QPushButton(RenameDialog)
        self.buttonSelectFolder.setObjectName("buttonSelectFolder")
        self.horizontalLayout.addWidget(self.buttonSelectFolder)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.checkDeleteAfterRename = QtWidgets.QCheckBox(RenameDialog)
        self.checkDeleteAfterRename.setObjectName("checkDeleteAfterRename")
        self.verticalLayout.addWidget(self.checkDeleteAfterRename)
        self.label_2 = QtWidgets.QLabel(RenameDialog)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.textSamples = QtWidgets.QTextEdit(RenameDialog)
        self.textSamples.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.textSamples.setReadOnly(True)
        self.textSamples.setObjectName("textSamples")
        self.verticalLayout.addWidget(self.textSamples)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.btnTest = QtWidgets.QPushButton(RenameDialog)
        self.btnTest.setObjectName("btnTest")
        self.horizontalLayout_2.addWidget(self.btnTest)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(RenameDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.horizontalLayout_2.addWidget(self.buttonBox)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.gridLayout.addLayout(self.verticalLayout, 0, 0, 1, 1)

        self.retranslateUi(RenameDialog)
        self.buttonBox.accepted.connect(RenameDialog.accept)
        self.buttonBox.rejected.connect(RenameDialog.reject)
        self.radioSameDir.clicked.connect(RenameDialog.switch_copy_to)
        self.radioRenameTo.clicked.connect(RenameDialog.switch_copy_to)
        self.buttonSelectFolder.clicked.connect(RenameDialog.select_dest_dir)
        self.btnTest.clicked.connect(RenameDialog.test)
        QtCore.QMetaObject.connectSlotsByName(RenameDialog)

    def retranslateUi(self, RenameDialog):
        _translate = QtCore.QCoreApplication.translate
        RenameDialog.setWindowTitle(_translate("RenameDialog", "Rename"))
        self.label.setText(_translate("RenameDialog", "Author pattern"))
        self.label_3.setText(_translate("RenameDialog", "Filename pattern"))
        self.radioSameDir.setText(_translate("RenameDialog", "Rename in same directory"))
        self.radioRenameTo.setText(_translate("RenameDialog", "Copy to:"))
        self.buttonSelectFolder.setText(_translate("RenameDialog", "Select"))
        self.checkDeleteAfterRename.setText(_translate("RenameDialog", "Delete source files after rename"))
        self.label_2.setText(_translate("RenameDialog", "Samples:"))
        self.btnTest.setText(_translate("RenameDialog", "Test"))

