#En esta version lee los datos de la base de datos directamente
#EN esta version se sacan los botones de lectura de sensores en configuracion
#
#
#1 pantalla negra
#2 variable tiemnpo refresco pantalla
#
#para instalar minimalbus:  apt search minimalmodbus      o    pip install minimalmodbus
#pip install matplotlib pandas
####import RPi.GPIO as GPIO

# para ejecutar en raspi
# /var/opt/release/ui $ python ui.py

import serial
import glob
import sys
import time 
import os
import csv
import subprocess
from datetime import timedelta
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QFrame, QPushButton,
    QLineEdit, QDialog, QMessageBox, QGridLayout,
    QFileDialog, QComboBox, QPushButton,
    QCheckBox, QScrollArea, QGroupBox,
    QDialogButtonBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QPointF, QPoint, QRectF
from PyQt6.QtGui import QPalette, QBrush, QPixmap, QPainter, QPen, QColor, QRadialGradient, QPainterPath, QPixmap
import sqlite3
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
plt.rcParams.update({
    'text.color': 'white',
    'axes.labelcolor': 'white',
    'xtick.color': 'white',
    'ytick.color': 'white',
    'axes.edgecolor': 'white',
})
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd

# Configuraciones generales
NOMBRE_EQUIPO = "TRATANK 79"
CLAVE_CORRECTA = "12345678"   ## clave para entrar en configuracion
CLAVE_BOTONES = "1234"       ##########clave para los botones de wifi on y remoto on
CANT_TANQUES = 8
NOMBRES_TANQUES = ["1BB", "1ES", "2BB", "2ES", "3BB", "3ES", "4BB", "4ES"]
ESTADO_VICTRON_CS=["APAGADO","","Falla","Bulk","Absorción","Flotación","","Equalización"]
#ESTADO_VICTRON_ERR=
VERSION = 'Version: 2P.112'
RUTA_DB = '/var/opt/release/db_status/db_status.db'   
ARCHIVO_CALIBRACION_CSV = '/var/opt/release/db_status/calibration.csv'  
SCRIPT_CALIBRACIONALTURA_PY= '/var/opt/release/run-calibration.sh'
FULL_SCREEN = True   #true es para full screen
CARPETA_CSV_LOG = "/var/opt/release/datalogs/"  
PUERTO_SENSORES='/dev/ttyUSB0'  #puerto serial de MODBUS
TIEMPO_REFRESCO_PANTALLA_PPAL=2000  #valor en ms
# Fin configuraciones
Tipo_Visualizacion = True  #elije el tipo de grafico historico a ver el cambio se debera realizar dfesde configuracion

class TecladoNumericoDialog(QDialog):
    def __init__(self, texto_inicial="",ocultar_texto = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Teclado Numérico")
        self.setFixedSize(250, 300)
        self.entrada = texto_inicial

        layout = QVBoxLayout()
        self.display = QLineEdit(self.entrada)
        # Configurar el modo de eco según el parámetro ocultar_texto
        self.display.setEchoMode(QLineEdit.EchoMode.Password if ocultar_texto else QLineEdit.EchoMode.Normal)
        #self.display.setEchoMode(QLineEdit.EchoMode.Password)
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFixedHeight(40)
        layout.addWidget(self.display)

        botones = [
            ('1', '2', '3'),
            ('4', '5', '6'),
            ('7', '8', '9'),
            ('Borrar', '0', 'OK')
        ]

        for fila in botones:
            fila_layout = QHBoxLayout()
            for texto in fila:
                btn = QPushButton(texto)
                btn.setFixedHeight(40)
                btn.clicked.connect(self.boton_presionado)
                fila_layout.addWidget(btn)
            layout.addLayout(fila_layout)

        self.setLayout(layout)
        self.resultado = None

    def boton_presionado(self):
        boton = self.sender()
        texto = boton.text()
        if texto == 'Borrar':
            self.display.setText(self.display.text()[:-1])
        elif texto == 'OK':
            self.resultado = self.display.text()
            self.accept()
        else:
            if len(self.display.text()) < 8:
                self.display.setText(self.display.text() + texto)


class DialogoClave(QDialog):
    def __init__(self, clave, parent=None):##########################
        super().__init__(parent)
        self.setWindowTitle("Ingreso de Clave")
        self.setFixedSize(300, 180)
        self.setStyleSheet("background-color: black; color: white;")
        self.clave_correcta = clave  ###################### <-- guardás la clave pasada por parámetro

        layout = QVBoxLayout()
        longitud = len(clave)
        self.label = QLabel(f"Ingrese la clave ({longitud} dígitos):")
        layout.addWidget(self.label)

        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setMaxLength(8)
        layout.addWidget(self.input)

        botones_layout = QHBoxLayout()
        self.boton_teclado = QPushButton("Teclado Numérico")
        self.boton_teclado.clicked.connect(self.abrir_teclado)
        botones_layout.addWidget(self.boton_teclado)

        self.boton_aceptar = QPushButton("Aceptar")
        self.boton_aceptar.clicked.connect(self.verificar_clave)
        botones_layout.addWidget(self.boton_aceptar)

        layout.addLayout(botones_layout)
        self.setLayout(layout)
        self.clave_valida = False

    def abrir_teclado(self):
        #teclado = TecladoNumericoDialog(texto_inicial=self.input.text(), parent=self)
        teclado = TecladoNumericoDialog(texto_inicial=self.input.text(), ocultar_texto=True, parent=self)
        if teclado.exec() == QDialog.DialogCode.Accepted and teclado.resultado is not None:
            self.input.setText(teclado.resultado)

    def verificar_clave(self):
        if self.input.text() == self.clave_correcta:  ################### <-- comparo con la clave recibida
            self.clave_valida = True
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Clave incorrecta")
            self.input.clear()

class Historico(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana_principal = ventana_principal
        self.setWindowTitle("Histórico de Datos")
        self.setFixedSize(1024, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.nombres_tanques = NOMBRES_TANQUES
        layout_principal = QVBoxLayout()

        # Menú desplegable para elegir archivo CSV
        self.selector_archivos = QComboBox()
        self.selector_archivos.addItem("Seleccione un archivo CSV...")
        self.selector_archivos.addItems(self.obtener_archivos_csv())
        self.selector_archivos.currentIndexChanged.connect(self.archivo_seleccionado)
        layout_principal.addWidget(self.selector_archivos)

        # Contenedor dividido: gráfico + controles
        layout_contenedor = QHBoxLayout()

        # Área de gráficos
        fig = Figure(figsize=(10, 8))
        fig.patch.set_alpha(0)  # Fondo de la figura transparente desde el inicio
        self.canvas = FigureCanvas(fig)
        self.canvas.setStyleSheet("background: transparent;")
        self.canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout_contenedor.addWidget(self.canvas, stretch=3)

        # Controles de visibilidad a la derecha
        self.checkbox_layout = QVBoxLayout()
        self.checkbox_layout.setSpacing(10)
        self.checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.checkbox_group = QGroupBox("Tanques")
        self.checkbox_group.setStyleSheet("QGroupBox { color: white; background-color: transparent; }")
        self.checkbox_group.setLayout(self.checkbox_layout)
        self.checkbox_group.setStyleSheet("QGroupBox { color: white; background-color: transparent; border: 1px solid white; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; top: 5px; }")


        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.checkbox_group)
        scroll.setFixedWidth(100)  #ancho del cuadrado que contiene a los checkbox
        scroll.setStyleSheet("background-color: transparent;")
        scroll.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout_contenedor.addWidget(scroll, stretch=0)
        layout_principal.addLayout(layout_contenedor)

        # Botón para volver
        boton_volver = QPushButton("Volver")
        boton_volver.clicked.connect(self.volver)
        layout_principal.addWidget(boton_volver, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout_principal)

    def obtener_archivos_csv(self):
        return glob.glob(f"{CARPETA_CSV_LOG}*.csv")

    def archivo_seleccionado(self, index):
        if index == 0:
            return
        archivo = self.selector_archivos.currentText()
        self.cargar_csv(archivo)

    def cargar_csv(self, archivo):
        try:
            df = pd.read_csv(archivo, sep=';', encoding='utf-8-sig')
            df.columns = [col.strip().upper().replace(" ", "_") for col in df.columns]
            if "TIMESTAMP" not in df.columns:
                raise ValueError("El archivo CSV debe contener una columna 'Tiempo UNIX'.")
            from datetime import timedelta
            df["FECHA_HORA"] = pd.to_datetime(df["TIMESTAMP"], unit="s") - timedelta(hours=3)
            #df["FECHA_HORA"] = pd.to_datetime(df["TIMESTAMP"], unit="s")

            with open(ARCHIVO_CALIBRACION_CSV, "r") as f:
                lineas = f.readlines()
                if len(lineas) < 2:
                    raise ValueError("El archivo calibration.txt debe tener al menos dos líneas.")
                valores = lineas[1].strip().split(";")
                if len(valores) < CANT_TANQUES:
                    raise ValueError(f"La segunda línea de calibration.txt debe tener al menos {CANT_TANQUES} valores separados por ';'.")
                limites_y = [float(valor) for valor in valores[:CANT_TANQUES]]

            self.df_actual = df
            self.limites_y = limites_y
            self.columnas_sondeo = [f"SONDEO_T{i}" for i in range(1, CANT_TANQUES + 1)]
            self.archivo_actual = archivo

            self.crear_checkboxes()
            self.actualizar_grafico()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el archivo:\n{e}")

    def crear_checkboxes(self):
        while self.checkbox_layout.count():
            child = self.checkbox_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.checkboxes = []
        for i, nombre in enumerate(self.nombres_tanques):
            cb = QCheckBox(nombre)
            cb.setChecked(True)
            #cb.setStyleSheet("background-color: transparent ;color: white;")  #color del texto a la derecha del checkbox
            cb.setStyleSheet("""
                QCheckBox {
                    background-color: transparent;
                    color: white;
                    font-size: 20px;           /* Tamaño del texto */
                    spacing: 12px;             /* Espacio entre la caja y el texto */
                }
                QCheckBox::indicator {
                    width: 24px;               /* Tamaño de la casilla */
                    height: 24px;
                }
            """)
            cb.stateChanged.connect(self.actualizar_grafico)
            self.checkbox_layout.addWidget(cb)
            self.checkboxes.append(cb)

        self.checkbox_layout.addStretch()

    def actualizar_grafico(self):
        try:
            import matplotlib.pyplot as plt

            df = self.df_actual
            limites_y = self.limites_y
            columnas = self.columnas_sondeo
            archivo = self.archivo_actual
            x = df["FECHA_HORA"]

            self.canvas.figure.clf()
            self.canvas.figure.patch.set_alpha(0)
            plt.rcParams.update({
                'text.color': 'white',
                'axes.labelcolor': 'white',
                'xtick.color': 'white',
                'ytick.color': 'white',
                'axes.edgecolor': 'white',
            })

            ax = self.canvas.figure.add_subplot(1, 1, 1)
            ax.set_facecolor("none")
            self.canvas.figure.patch.set_facecolor('none')
            ax.set_facecolor("none")
            ax.set_title(f"Archivo: {archivo}", color='white')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.tick_params(axis='x', rotation=90)  # Opcional: gira las fechas para que no se pisen
            ax.set_title(f"Archivo: {archivo}")
            colores = plt.cm.get_cmap('tab10', len(columnas))

            for i, (col, cb) in enumerate(zip(self.columnas_sondeo, self.checkboxes)):
                if cb.isChecked() and col in df.columns:
                    ax.plot(x, df[col], label=cb.text(), color=colores(i))



            ax.set_ylabel("Sondeo", color='white')
            ax.set_xlabel("Índice", color='white')
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            ax.grid(True, color='white')
            legend = ax.legend(loc='upper right', fontsize='small') #Cuadro de referencia de arriba a la derecha
            legend.get_frame().set_facecolor('#999999')  # Gris claro de fondo
            #legend.get_frame().set_alpha(0)  # Fondo transparente
            #legend.get_frame().set_facecolor('black')     # fondo negro
            #legend.get_frame().set_edgecolor('white')     # borde blanco
            #legend.get_frame().set_alpha(0.7)             # opacidad
            ax.set_ylim(0, max(limites_y))

            self.canvas.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el gráfico:\n{e}")

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(
    #        self.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
    #        Qt.TransformationMode.SmoothTransformation
    #    )
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)


    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)



    def resizeEvent(self, event):
        self.actualizar_fondo()
        super().resizeEvent(event)

    def volver(self):
        self.hide()
        self.ventana_principal.show()


class Historico_Canales(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana_principal = ventana_principal
        self.setWindowTitle("Histórico de Datos")
        self.setFixedSize(1024, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        layout_principal = QVBoxLayout()

        # Menú desplegable para elegir archivo CSV
        self.selector_archivos = QComboBox()
        self.selector_archivos.addItem("Seleccione un archivo CSV...")
        self.selector_archivos.addItems(self.obtener_archivos_csv())
        self.selector_archivos.currentIndexChanged.connect(self.archivo_seleccionado)
        layout_principal.addWidget(self.selector_archivos)

        # Área de gráficos
        fig = Figure(figsize=(10, 8))
        fig.patch.set_alpha(0)  # Fondo de la figura transparente desde el inicio
        self.canvas = FigureCanvas(fig)
        self.canvas.setStyleSheet("background: transparent;")
        self.canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout_principal.addWidget(self.canvas, stretch=3)

        # Botón para volver
        boton_volver = QPushButton("Volver")
        boton_volver.clicked.connect(self.volver)
        layout_principal.addWidget(boton_volver, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout_principal)

    def obtener_archivos_csv(self):
        archivos = glob.glob(f"{CARPETA_CSV_LOG}*.csv")
        return archivos

    def archivo_seleccionado(self, index):
        if index == 0:
            return  # Primer ítem es solo informativo
        archivo = self.selector_archivos.currentText()
        self.cargar_csv(archivo)

    def cargar_csv(self, archivo):
        try:
            import matplotlib.pyplot as plt
            from matplotlib.dates import DateFormatter

            df = pd.read_csv(archivo, sep=';', encoding='utf-8-sig')
            df.columns = [col.strip().upper().replace(" ", "_") for col in df.columns]
            if "TIMESTAMP" not in df.columns:
                raise ValueError("El archivo CSV debe contener una columna 'Tiempo UNIX'.")
            from datetime import timedelta
            df["FECHA_HORA"] = pd.to_datetime(df["TIMESTAMP"], unit="s") - timedelta(hours=3)
            #df["FECHA_HORA"] = pd.to_datetime(df["TIMESTAMP"], unit="s")

            with open(ARCHIVO_CALIBRACION_CSV, "r") as f:
                lineas = f.readlines()
                if len(lineas) < 2:
                    raise ValueError("El archivo calibration.txt debe tener al menos dos líneas.")
                linea = lineas[1].strip()
                valores = linea.split(";")
                if len(valores) < CANT_TANQUES:
                    raise ValueError(f"La segunda línea de calibration.txt debe tener al menos {CANT_TANQUES} valores separados por ';'.")
                limites_y = [float(valor) for valor in valores[:CANT_TANQUES]]

            columnas_sondeo = [f"SONDEO_T{i}" for i in range(1, CANT_TANQUES + 1)]
            x = df["FECHA_HORA"]

            self.canvas.figure.clf()
            self.canvas.figure.patch.set_alpha(0)

            plt.rcParams.update({
                'text.color': 'white',
                'axes.labelcolor': 'white',
                'xtick.color': 'white',
                'ytick.color': 'white',
                'axes.edgecolor': 'white',
            })

            time_formatter = DateFormatter('%H:%M:%S')  # <--- Mostrar solo la hora

            for i, col in enumerate(columnas_sondeo):
                ax = self.canvas.figure.add_subplot(CANT_TANQUES, 1, i + 1)
                ax.set_facecolor("none")

                if col in df.columns:
                    ax.plot(x, df[col], label=col, color='blue')
                    ax.set_ylabel(f"T{i+1}", color='white')
                    ax.set_ylim(0, limites_y[i])
                    ax.grid(True, color='white')
                    ax.tick_params(axis='y', colors='white')
                    ax.xaxis.set_major_formatter(time_formatter)  # <--- Aplicar formato al eje X

                    if i == CANT_TANQUES - 1:
                        ax.set_xlabel("Hora", color='white')
                    else:
                        ax.tick_params(labelbottom=False)

                    if i == 0:
                        ax.set_title(f"Archivo: {archivo}", color='white')
                else:
                    ax.set_ylabel(col)
                    ax.text(0.5, 0.5, f"{col} no encontrado", transform=ax.transAxes, ha="center", va="center")
                    ax.tick_params(axis='x', colors='white')
                    ax.tick_params(axis='y', colors='white')

            self.canvas.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el archivo:\n{e}")

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)

    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)



    def resizeEvent(self, event):
        self.actualizar_fondo()
        super().resizeEvent(event)


    def volver(self):
        self.hide()
        self.ventana_principal.show()


class TanqueWidget(QFrame):    #Cuadrado y barra de cada tanque
    def __init__(self, nombre, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 380)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                border: 2px solid white;
                border-radius: 10px;
                background: qlineargradient(
                spread:pad,
                x1:0, y1:1,
                x2:0, y2:0,
                stop:0 yellow,
                stop:1 orange
                 );
            }
        """)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.etiqueta_titulo = QLabel(nombre)  # Mostrar nombre del tanque arriba de este

        self.etiqueta_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_titulo.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: black;
            border: 2px solid transparent;
            padding: 4px;
            border-radius: 0px;
            background-color: transparent;
        """)
        layout.addWidget(self.etiqueta_titulo)

        self.etiqueta_valor_num = QLabel("0")
        self.etiqueta_valor_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_valor_num.setStyleSheet("font-size: 20px;border: transparent; background-color: transparent;")
        
        layout.addWidget(self.etiqueta_valor_num)

        self.barra = QProgressBar()
        self.barra.setOrientation(Qt.Orientation.Vertical)
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setTextVisible(False)
        self.barra.setFixedSize(50, 250)
        self.barra.setStyleSheet("""
            QProgressBar {
                border: 2px solid white;
                border-radius: 5px;
                background: #111;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #00FF00;
                margin: 1px;
            }
        """)
        
        layout.addWidget(self.barra, alignment=Qt.AlignmentFlag.AlignCenter)

        self.etiqueta_porcentaje = QLabel("0%")
        self.etiqueta_porcentaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etiqueta_porcentaje.setStyleSheet("font-size: 20px;border: transparent; background-color: yellow;")
        layout.addWidget(self.etiqueta_porcentaje)

        self.setLayout(layout)

    def actualizar_valores(self, valor_absoluto, porcentaje):
        self.etiqueta_valor_num.setText(f"{valor_absoluto}")
        self.etiqueta_porcentaje.setText(f"{porcentaje:.1f}%")
        self.barra.setValue(valor_absoluto)


class Configuracion(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana_principal = ventana_principal
        self.setWindowTitle("CONFIGURACION")
        self.setFixedSize(1024, 600)
        #self.showFullScreen()

        #saca la cruz de cierre 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Diseño principal
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        # Título de la ventana
        titulo = QLabel("Configuración de Tanques")
        titulo.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: white;
            padding: 10px;
        """)
        titulo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(titulo)

        # Campos para cada tanque
        self.campos_tanques = []
        for i in range(CANT_TANQUES):
            fila = QHBoxLayout()
            etiqueta_tanque = QLabel(f"Valor Tanque {i+1}:")
            etiqueta_tanque.setStyleSheet("color: white; font-size: 16px;")
            etiqueta_tanque.setFixedWidth(150)

            campo = QLineEdit()
            campo.setFixedWidth(200)
            self.campos_tanques.append(campo)

            boton_teclado = QPushButton("Teclado")
            boton_teclado.setFixedWidth(60)
            boton_teclado.setFixedHeight(20)  # Reduce la altura del botón
            boton_teclado.setStyleSheet("""
                font-size: 12px;  /* Tamaño del texto más pequeño */
                font-weight: bold;
                border-radius: 5px;  /* Bordes redondeados más pequeños */
                padding: 3px;  /* Menor espacio interno */
                background-color: #333; /* Color de fondo */
                color: white; /* Color del texto */
            """)
            boton_teclado.clicked.connect(lambda _, c=campo: self.abrir_teclado_numerico(c))


            etiqueta_tanque.setAlignment(Qt.AlignmentFlag.AlignTop)
            fila.setAlignment(Qt.AlignmentFlag.AlignTop)
            fila.addWidget(etiqueta_tanque)
            fila.addWidget(campo)
            fila.addWidget(boton_teclado)
            layout.addLayout(fila)
            
            
        botones_layout = QHBoxLayout()

        self.boton_cargar_datos = QPushButton("Autocalibracion")
        self.boton_cargar_datos.clicked.connect(self.cargar_datos_csv)
        botones_layout.addWidget(self.boton_cargar_datos)

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.clicked.connect(self.guardar_valores)
        botones_layout.addWidget(self.boton_guardar)

        self.boton_volver = QPushButton("Volver")
        self.boton_volver.clicked.connect(self.volver)
        botones_layout.addWidget(self.boton_volver)

        # Botón para cerrar el programa
        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        self.boton_cerrar.clicked.connect(self.cerrar_programa)
        botones_layout.addWidget(self.boton_cerrar)

        layout.addLayout(botones_layout)
        self.setLayout(layout)

        layout.addLayout(botones_layout)
        self.setLayout(layout)

        self.cargar_valores_desde_archivo()
        self.actualizar_fondo()

    def abrir_teclado_numerico(self, campo):
        teclado = TecladoNumericoDialog(texto_inicial=campo.text(), ocultar_texto=False, parent=self)
        if teclado.exec() == QDialog.DialogCode.Accepted and teclado.resultado is not None:
            campo.setText(teclado.resultado)
    
    def cerrar_programa(self):
        QApplication.quit()

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)

    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)





    def resizeEvent(self, event):
        self.actualizar_fondo()
        super().resizeEvent(event)

    def cargar_valores_desde_archivo(self):
        try:
            with open(ARCHIVO_CALIBRACION_CSV, newline='') as csvfile:
                lector = csv.reader(csvfile, delimiter=';')  # Especificar el delimitador
                next(lector, None)  # Saltar la cabecera
                fila = next(lector, [])  # Leer la primera fila de valores

                # Precargar los valores en los campos, asignar "0" si faltan
                for i in range(CANT_TANQUES):
                    if i < len(fila):
                        self.campos_tanques[i].setText(fila[i])  # Valor del archivo
                    else:
                        self.campos_tanques[i].setText("0")  # Valor predeterminado para tanques faltantes
        except Exception as e:
            QMessageBox.warning(self, "Advertencia", f"No se pudo leer el archivo de calibracion\n{e}")

    def leerDatoTanqueDBSQLite(self,DATO):
            import sqlite3
            database_file = RUTA_DB
            conn = sqlite3.connect(database_file)
            cursor = conn.cursor()
            CONSULTA = 'SELECT var_valor FROM tanques WHERE var_name==' + "'" + DATO + "'" + ";"
            cursor.execute(CONSULTA)
            rows = cursor.fetchall()
            for row in rows:       
                X = row[0]
            return X
            conn.close()

    def cargar_datos_csv(self):
        try:
            # Ejecutar el script CalibracionAltura.py antes de cargar los datos
            subprocess.run(["bash", SCRIPT_CALIBRACIONALTURA_PY], check=True)

            # Recargar los valores en la pantalla
            self.cargar_valores_desde_archivo()

            # Mostrar mensaje de éxito
            msg = QMessageBox(self)
            msg.setWindowTitle("Éxito")
            msg.setText("Datos cargados correctamente.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()

        except Exception as e:
            # Manejar errores si no pudo abrir la base y muestra un mensaje de advertencia
            msg = QMessageBox(self)
            msg.setWindowTitle("Error")
            msg.setText(f"No se pudo cargar los datos.\n{e}")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()


    def guardar_valores(self):  # Pisa los valores en el archivo de calibración
        valores_a_guardar = []
        for i, campo in enumerate(self.campos_tanques):
            texto = campo.text()
            try:
                valor = int(texto)
                if 0 <= valor <= 10000:
                    valores_a_guardar.append(str(valor))
                else:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Error", f"Valor inválido en Tanque {i + 1}. Debe ser entero entre 0 y 10000.")
                return
        timestamp_actual = int(time.time())  # Obtener el tiempo en segundos desde el Epoch
        valores_a_guardar.append(str(timestamp_actual))
        try:
            lineas = []
            if os.path.exists(ARCHIVO_CALIBRACION_CSV):
                with open(ARCHIVO_CALIBRACION_CSV, "r") as csvfile:
                    lineas = csvfile.readlines()

            nueva_segunda_linea = ";".join(valores_a_guardar) + "\n"
            if len(lineas) > 1:
                lineas[1] = nueva_segunda_linea
            else:
                lineas.append(nueva_segunda_linea)

            with open(ARCHIVO_CALIBRACION_CSV, "w", newline='') as csvfile:
                csvfile.writelines(lineas)

            msg = QMessageBox(self)
            msg.setWindowTitle("Guardado")
            msg.setText("Valores guardados correctamente en calibracion.csv")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            print(f"Error al guardar el archivo: {e}")  # Imprime el error en la pantalla
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo\n{e}")



    def volver(self):
        for i, campo in enumerate(self.campos_tanques):
            texto = campo.text()
            try:
                valor = int(texto)
                if 0 <= valor <= 100:
                    porcentaje = int((valor / 100) * 100)  # Porcentaje fijo
                    if i < len(self.ventana_principal.tanques):
                        self.ventana_principal.tanques[i].actualizar_valores(valor, porcentaje)
                else:
                    raise ValueError
            except ValueError:
                if i < len(self.ventana_principal.tanques):
                    self.ventana_principal.tanques[i].actualizar_valores(0, 0)

        self.hide()
        self.ventana_principal.show()


    def inicializar_instrumento(self,puerto, direccion):
        instrumento = minimalmodbus.Instrument(puerto, direccion)
        instrumento.serial.baudrate = 9600
        instrumento.serial.bytesize = 8
        instrumento.serial.parity = serial.PARITY_NONE
        instrumento.serial.stopbits = 1
        instrumento.serial.timeout = 0.10
        instrumento.mode = minimalmodbus.MODE_RTU
        instrumento.clear_buffers_before_each_transaction = True
        instrumento.close_port_after_each_call = True
        return instrumento

    

class Energia(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana_principal = ventana_principal
        self.setWindowTitle("ENERGIA")
        self.setFixedSize(1024, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.valor_panel_solar_valor_3 = 0  # o None
        self.valor_carga_valor_5 = 0
        self.v4=0
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        titulo = QLabel("Gestión de Energía")
        titulo.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: white;
            padding: 10px;
        """)
        titulo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(titulo)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(20, 20, 20, 20)
        grid_layout.setSpacing(20)

        # Imagen izquierda: panel solar
        self.panel_solar_label = CuadradoPV()
        grid_layout.addWidget(self.panel_solar_label, 0, 0)

        # Imagen central: victron
        self.victron_label = LogoVictronWidget()
        grid_layout.addWidget(self.victron_label, 0, 1)

        # Imagen inferior: batería (debajo de victron)
        grid_layout.addItem(QSpacerItem(20, 120, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), 1, 1)
        self.bateria_label = CuadradoBateria()
        grid_layout.addWidget(self.bateria_label, 3, 1)
        
        # Imagen derecha: raspi
        self.raspi_label = CuadradoLoad()
        grid_layout.addWidget(self.raspi_label, 0, 2)

        #self.raspi_valor = QLabel("0 Ampere")
        #self.raspi_valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.raspi_valor.setStyleSheet("color: white; font-weight: bold; font-size: 24px;")
        #grid_layout.addWidget(self.raspi_valor, 1, 2)

        layout.addLayout(grid_layout)

        layout_botones = QHBoxLayout()
        layout_botones.addStretch()  # Empuja los botones a la derecha

        boton_historico_energia = QPushButton("Histórico")
        boton_historico_energia.setStyleSheet("font-size: 18px; font-weight: bold;")
        boton_historico_energia.clicked.connect(self.historico)
        layout_botones.addWidget(boton_historico_energia)

        boton_volver = QPushButton("Volver")
        boton_volver.setStyleSheet("font-size: 18px; font-weight: bold;")
        boton_volver.clicked.connect(self.volver)
        layout_botones.addWidget(boton_volver)

        # Agregás el layout de botones al layout principal
        layout.addLayout(layout_botones)
        self.setLayout(layout)
        self.actualizar_fondo()

        # Capa de dibujo
        self.capa_dibujo = CapaDibujo(self, self)
        self.capa_dibujo.setGeometry(self.rect())
        self.capa_dibujo.set_widgets_para_linea(
        self.panel_solar_label,
        self.victron_label,
        raspi=self.raspi_label,
        bateria=self.bateria_label
        )
 
        self.timer_csv = QTimer(self)
        self.timer_csv.timeout.connect(self.actualizar_datos)
        self.timer_csv.start(15000) #tiempo de recarga de datos desde la base sql
        self.actualizar_datos()

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)

    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)


    def leerDatoDBSQLite(self, DATO):
        database_file = RUTA_DB
        conn = sqlite3.connect(database_file)
        cursor = conn.cursor()
        CONSULTA = 'SELECT var_valor FROM status WHERE var_name==?'
        cursor.execute(CONSULTA, (DATO,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def actualizar_datos(self):
        try:

            v1 = float(self.leerDatoDBSQLite("DB_VDATA_VPV")) / 1000
            v2 = float(self.leerDatoDBSQLite("DB_VDATA_PPV"))
            valor_panel_solar_valor_3 = v2 / v1 if v1 != 0 else 0
            self.valor_panel_solar_valor_3 = valor_panel_solar_valor_3
            self.panel_solar_label.set_valores(
                f"{v1:.1f} V",
                f"{v2:.1f} W",
                f"{valor_panel_solar_valor_3:.1f} A"
            )


            v3 = float(self.leerDatoDBSQLite("DB_VDATA_V")) / 1000
            v4 = float(self.leerDatoDBSQLite("DB_VDATA_I")) / 1000
            self.v4 = v4
            self.bateria_label.set_valores(f"{v3} V", f"{v4} A")
           

            v5 = float(self.leerDatoDBSQLite("DB_VDATA_IL")) / 1000
            self.valor_carga_valor_5 = v5
            self.raspi_label.set_valor(f"{v5:.1f} A") 




            self.capa_dibujo.update_lineas()


            cs_valor_raw = self.leerDatoDBSQLite("DB_VDATA_CS")
            try:
                cs_valor = int(cs_valor_raw)
                texto_estado = ESTADO_VICTRON_CS[cs_valor] if 0 <= cs_valor < len(ESTADO_VICTRON_CS) else "Desconocido"
            except:
                texto_estado = "Desconocido"
            self.victron_label.set_texto_estado(f"{texto_estado}")
            self.capa_dibujo.update_lineas()

        except Exception as e:
            print(f"[ERROR actualizar_datos] {e}")

        #cs_valor = self.leerDatoDBSQLite("DB_VDATA_CS")
        #cs_valor = int(cs_valor)  # convertir a entero
        #texto_estado = ESTADO_VICTRON_CS[cs_valor]
        #self.victron_valor_cs.setText(f"{texto_estado}")

    def resizeEvent(self, event):
        self.actualizar_fondo()
        self.capa_dibujo.setGeometry(self.rect())
        self.capa_dibujo.update_lineas()
        super().resizeEvent(event)

    def volver(self):
        self.timer_csv.stop()
        self.hide()
        self.ventana_principal.show()

    def historico(self):
        if not hasattr(self, 'Historico_Energia') or self.Historico_Energia is None:
            self.Historico_Energia = Historico_Energia(self)
        self.Historico_Energia.showFullScreen()
        self.hide()


class CapaDibujo(QWidget):
    def __init__(self, parent=None, energia=None):
        super().__init__(parent)
        self.energia = energia
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.lineas = []  
        self.panel = None
        self.victron = None
        self.raspi = None
        self.bateria = None

        self.timer_anim = QTimer(self)
        self.timer_anim.timeout.connect(self.actualizar_animacion)
        self.timer_anim.start(50)  # 20 fps aprox.

        self.offset = 0  # Desplazamiento horizontal de la animación
        self.circulo_radio = 10  # radio del círculo
        self.separacion = 25  # separación entre círculos en pixeles

    def set_widgets_para_linea(self, panel, victron, raspi=None, bateria=None):
        self.panel = panel
        self.victron = victron
        self.raspi = raspi
        self.bateria = bateria
        self.update_lineas()

    def actualizar_animacion(self):
        self.offset = (self.offset + 2) % 99999  # en vez de +2 se puede ajustar velocidad de puntos
        self.update()

    def update_lineas(self):
        self.lineas.clear()
        if self.panel and self.victron:
            p1 = self.mapFromGlobal(self.panel.mapToGlobal(QPoint(200, 100)))
            p2 = self.mapFromGlobal(self.victron.mapToGlobal(QPoint(0, 100)))
            if not self.energia or self.energia.valor_panel_solar_valor_3 != 0:
                self.lineas.append((p1.x(), p1.y(), p2.x(), p2.y(), 1))

        if self.victron and self.raspi:
            p1 = self.mapFromGlobal(self.victron.mapToGlobal(QPoint(200, 100)))
            p2 = self.mapFromGlobal(self.raspi.mapToGlobal(QPoint(0, 100)))


            if self.energia.valor_carga_valor_5 != 0:
                self.lineas.append((p1.x(), p1.y(), p2.x(), p2.y(), 1))

        if self.victron and self.bateria and self.energia.v4 !=0:
            try:
                v4 = float(self.energia.leerDatoDBSQLite("DB_VDATA_I"))
            except:
                v4 = 0

            direccion = 1 if v4 >= 0 else -1
            p1 = self.mapFromGlobal(self.victron.mapToGlobal(QPoint(100, 200)))
            p2 = self.mapFromGlobal(self.bateria.mapToGlobal(QPoint(100, 0)))
            
            
            if direccion == -1:
                p1, p2 = p2, p1

            self.lineas.append((p1.x(), p1.y(), p2.x(), p2.y(), direccion))

        self.update()

    def paintEvent(self, event):


        painter = QPainter(self)

        for x1, y1, x2, y2, direccion in self.lineas:
            pen = QPen(Qt.GlobalColor.green if direccion == 1 else Qt.GlobalColor.cyan, 3)
            painter.setPen(pen)
            painter.drawLine(x1, y1, x2, y2)

            dx = x2 - x1
            dy = y2 - y1
            length = (dx ** 2 + dy ** 2) ** 0.5
            if length == 0:
                continue
            vx = dx / length
            vy = dy / length

            num_circulos = int(length // self.separacion) + 0 #aca puede ir un +2

            for i in range(num_circulos):
                dist = (i * self.separacion + self.offset) % length
                cx = x1 + vx * dist
                cy = y1 + vy * dist

                grad = QRadialGradient(QPointF(cx, cy), self.circulo_radio)
                grad.setColorAt(0, QColor(120, 255, 120, 200))  # centro verde claro
                grad.setColorAt(1, QColor(120, 255, 120, 0))    # borde transparente

                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(cx, cy), self.circulo_radio, self.circulo_radio)

class LogoVictronWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.logo = QPixmap("logo_victron.png")  # Carga la imagen solo una vez
        self.texto_estado = "Desconocido"  # Texto por defecto

    def set_texto_estado(self, texto):
        self.texto_estado = texto
        self.update()  # Redibuja el widget

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dimensiones del rectángulo principal
        x, y, w, h = 0, 0, self.width(), self.height()
        radio = 6

        # Colores
        fondo_azul = QColor("#4589cf")
        color_linea = QColor("#dc5c00")

        # Dibuja fondo principal con esquinas redondeadas
        fondo = QRectF(x, y, w, h)
        painter.setBrush(fondo_azul)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fondo, radio, radio)

        # === Línea roja horizontal en la mitad del cuadro ===
        y_linea_roja = y + int(h * 0.23)  # 40% desde la parte superior  # Mitad del rectángulo
        painter.setPen(QPen(color_linea, 10))  # Línea gruesa y roja
        painter.drawLine(x+5, y_linea_roja, x + w-5, y_linea_roja)

        # Superposición del logo centrado
        if not self.logo.isNull():
            escala = 0.8
            desplazamiento = 30
            ancho = int(self.logo.width() * escala)
            alto = int(self.logo.height() * escala)
            logo_escalado = self.logo.scaled(
                ancho,
                alto,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logo_x = x + (w - ancho) // 2
            logo_y = y + (h - alto) // 2 - desplazamiento
            painter.drawPixmap(logo_x, logo_y, logo_escalado)

        # Mostrar texto dinámico (estado Victron CS)
        painter.setPen(QColor("#fef5ce"))
        fuente = painter.font()
        fuente.setPointSize(14)
        fuente.setBold(True)
        painter.setFont(fuente)

        altura = h // 5
        rect_texto = QRectF(x, y, w, altura)
        painter.drawText(rect_texto, Qt.AlignmentFlag.AlignCenter, self.texto_estado)

class CuadradoPV(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.valor_v = "0 V"
        self.valor_w = "0 W"
        self.valor_a = "0 A"

        # Cargar logo Victron una vez
        self.logo = QPixmap("sol.png")

    def set_valores(self, voltaje, potencia, corriente):
        self.valor_v = voltaje
        self.valor_w = potencia
        self.valor_a = corriente
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)


        # Dimensiones del rectángulo principal
        x, y, w, h = 0, 0, self.width(), self.height()
        radio = 6
        altura_franja = h // 5

        # Colores
        Naranja_oscuro = QColor("#f39c11")
        Naranja_claro = QColor("#f5b54e")

        # Fondo  oscuro con bordes redondeados
        fondo = QRectF(x, y, w, h)
        painter.setBrush(Naranja_oscuro)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fondo, radio, radio)

        # Franja superior con esquinas redondeadas solo arriba
        franja = QRectF(x, y, w, altura_franja)
        path_franja = QPainterPath()
        path_franja.moveTo(x, y + altura_franja)
        path_franja.lineTo(x, y + radio)
        path_franja.quadTo(x, y, x + radio, y)
        path_franja.lineTo(x + w - radio, y)
        path_franja.quadTo(x + w, y, x + w, y + radio)
        path_franja.lineTo(x + w, y + altura_franja)
        path_franja.closeSubpath()

        painter.setBrush(Naranja_claro)
        painter.drawPath(path_franja)

        # Texto sobre la franja clara
        painter.setPen(QColor("#fef5ce"))
        fuente = painter.font()
        fuente.setPointSize(16)
        fuente.setBold(True)
        painter.setFont(fuente)

        texto = "PANEL PV"
        rect_texto = QRectF(x, y, w, altura_franja)
        painter.drawText(rect_texto, Qt.AlignmentFlag.AlignCenter, texto)

        # Valores: voltaje, potencia y corriente
        painter.setPen(QColor("#ffffff"))
        fuente.setPointSize(12)
        painter.setFont(fuente)

        painter.drawText(QRectF(x, y + altura_franja + 20, w, 25), Qt.AlignmentFlag.AlignCenter, self.valor_v)
        painter.drawText(QRectF(x, y + altura_franja + 45, w, 25), Qt.AlignmentFlag.AlignCenter, self.valor_w)
        painter.drawText(QRectF(x, y + altura_franja + 70, w, 25), Qt.AlignmentFlag.AlignCenter, self.valor_a)

        
         # --- Superponer logo en esquina inferior derecha ---
        if not self.logo.isNull():
            escala = 1  # reduce el tamaño
            ancho = int(self.logo.width() * escala)
            alto = int(self.logo.height() * escala)
            logo_escalado = self.logo.scaled(ancho, alto, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            margen = 8  # separación del borde
            pos_x = w - ancho - margen
            pos_y = h - alto - margen
            painter.drawPixmap(pos_x, pos_y, logo_escalado)







class CuadradoLoad(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.valor = "0 A"  # Valor inicial

    def set_valor(self, valor):
        self.valor = valor
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)


        # Dimensiones del rectángulo principal
        x, y, w, h = 0, 0, self.width(), self.height()
        radio = 6
        altura_franja = h // 5

        # Colores
        celeste_oscuro = QColor("#26ae60")
        celeste_claro = QColor("#2dcb6f")

        # Fondo celeste oscuro con bordes redondeados
        fondo = QRectF(x, y, w, h)
        painter.setBrush(celeste_oscuro)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fondo, radio, radio)

        # Franja superior con esquinas redondeadas solo arriba
        franja = QRectF(x, y, w, altura_franja)
        path_franja = QPainterPath()
        path_franja.moveTo(x, y + altura_franja)
        path_franja.lineTo(x, y + radio)
        path_franja.quadTo(x, y, x + radio, y)
        path_franja.lineTo(x + w - radio, y)
        path_franja.quadTo(x + w, y, x + w, y + radio)
        path_franja.lineTo(x + w, y + altura_franja)
        path_franja.closeSubpath()

        painter.setBrush(celeste_claro)
        painter.drawPath(path_franja)

        # Texto sobre la franja clara
        painter.setPen(QColor("#a8efcd"))
        fuente = painter.font()
        fuente.setPointSize(16)
        fuente.setBold(True)
        painter.setFont(fuente)

        texto = "CARGA CC"
        rect_texto = QRectF(x, y, w, altura_franja)
        painter.drawText(rect_texto, Qt.AlignmentFlag.AlignCenter, texto)

        # Valor dinámico
        painter.setPen(QColor("#ffffff"))
        fuente.setPointSize(14)
        painter.setFont(fuente)
        painter.drawText(QRectF(x, y + altura_franja + 40, w, 30), Qt.AlignmentFlag.AlignCenter, self.valor)


class CuadradoBateria(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 150)
        self.voltaje = "0 V"
        self.corriente = "0 A"
        self.valor_negativo = "-"
        self.valor_positivo = "+"

    def set_valores(self, voltaje, corriente):
        self.voltaje = voltaje
        self.corriente = corriente
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)


        # Dimensiones del rectángulo principal
        x, y, w, h = 0, 0, self.width(), self.height()
        radio = 6
        altura_franja = h // 8

        # Colores
        celeste_oscuro = QColor("#4589cf")
        celeste_claro = QColor("#26c39d")

        # Fondo celeste oscuro con bordes redondeados
        fondo = QRectF(x, y, w, h)
        painter.setBrush(celeste_oscuro)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fondo, radio, radio)

        # Franja superior con esquinas redondeadas solo arriba
        franja = QRectF(x, y, w, altura_franja)
        path_franja = QPainterPath()
        path_franja.moveTo(x, y + altura_franja)
        path_franja.lineTo(x, y + radio)
        path_franja.quadTo(x, y, x + radio, y)
        path_franja.lineTo(x + w - radio, y)
        path_franja.quadTo(x + w, y, x + w, y + radio)
        path_franja.lineTo(x + w, y + altura_franja)
        path_franja.closeSubpath()

        painter.setBrush(celeste_claro)
        painter.drawPath(path_franja)

 #      #Texto "BATERÍA"
        painter.setPen(QColor("#fef5ce"))
        fuente = painter.font()
        fuente.setPointSize(14)
        fuente.setBold(True)
        painter.setFont(fuente)
        painter.drawText(QRectF(x, y, w, altura_franja), Qt.AlignmentFlag.AlignCenter, "BATERÍA")

        # Datos: voltaje y corriente
        painter.setPen(QColor("#ffffff"))
        fuente.setPointSize(12)
        painter.setFont(fuente)

        painter.drawText(QRectF(x, y + altura_franja + 20, w, 30), Qt.AlignmentFlag.AlignCenter, self.voltaje)
        painter.drawText(QRectF(x, y + altura_franja + 50, w, 30), Qt.AlignmentFlag.AlignCenter, self.corriente)

        fuente.setPointSize(14)
        painter.setFont(fuente)
        painter.drawText(QRectF(x-80, y + altura_franja + 5, w, 10), Qt.AlignmentFlag.AlignCenter, self.valor_negativo)
        painter.drawText(QRectF(x+80, y + altura_franja + 5, w, 10), Qt.AlignmentFlag.AlignCenter, self.valor_positivo)


class Historico_Energia(QWidget):
    def __init__(self, ventana_principal):
        super().__init__()
        self.ventana_principal = ventana_principal
        self.setWindowTitle("Histórico Energía")
        self.setFixedSize(1024, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        layout_principal = QVBoxLayout()

        # Menú desplegable para elegir archivo CSV
        self.selector_archivos = QComboBox()
        self.selector_archivos.addItem("Seleccione un archivo CSV...")
        self.selector_archivos.addItems(self.obtener_archivos_csv())
        self.selector_archivos.currentIndexChanged.connect(self.archivo_seleccionado)
        layout_principal.addWidget(self.selector_archivos)

        # Área de gráficos
        fig = Figure(figsize=(10, 8))
        fig.patch.set_alpha(0)
        self.canvas = FigureCanvas(fig)
        self.canvas.setStyleSheet("background: transparent;")
        self.canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout_principal.addWidget(self.canvas, stretch=3)

        # Botones
        layout_botones = QHBoxLayout()
        layout_botones.addStretch()

        boton_volver = QPushButton("Volver")
        boton_volver.setStyleSheet("font-size: 18px; font-weight: bold;")
        boton_volver.clicked.connect(self.volver)
        layout_botones.addWidget(boton_volver)

        layout_principal.addLayout(layout_botones)
        self.setLayout(layout_principal)

    def obtener_archivos_csv(self):
        return glob.glob(f"{CARPETA_CSV_LOG}*.csv")

    def archivo_seleccionado(self, index):
        if index == 0:
            return
        archivo = self.selector_archivos.currentText()
        self.cargar_csv(archivo)

    def cargar_csv(self, archivo):
        try:
            import matplotlib.pyplot as plt
            from matplotlib.dates import DateFormatter
            from datetime import timedelta

            df = pd.read_csv(archivo, sep=';', encoding='utf-8-sig')
            df.columns = [col.strip().upper().replace(" ", "_") for col in df.columns]

            if "TIMESTAMP" not in df.columns:
                raise ValueError("El archivo debe contener la columna 'TIMESTAMP'.")

            df["FECHA_HORA"] = pd.to_datetime(df["TIMESTAMP"], unit="s") - timedelta(hours=3)

            columnas_requeridas = ["VDATA_I", "VDATA_VPV", "VDATA_V", "VDATA_IL","VDATA_PPV"]
            columnas_presentes = [col for col in columnas_requeridas if col in df.columns]

            if not columnas_presentes:
                raise ValueError("Ninguna de las columnas requeridas fue encontrada.")

            x = df["FECHA_HORA"]

            self.canvas.figure.clf()
            self.canvas.figure.patch.set_alpha(0)

            plt.rcParams.update({
                'text.color': 'white',
                'axes.labelcolor': 'white',
                'xtick.color': 'white',
                'ytick.color': 'white',
                'axes.edgecolor': 'white',
            })

            formatter = DateFormatter('%H:%M:%S')

            colores_personalizados = ["red", "green", "blue", "orange"]
            for i, col in enumerate(columnas_presentes):
                ax = self.canvas.figure.add_subplot(len(columnas_presentes), 1, i + 1)
                ax.set_facecolor("none")
                color = colores_personalizados[i % len(colores_personalizados)]  # usa el color correspondiente
                ax.plot(x, df[col], label=col, color=color)
                ax.set_ylabel(col, color='white')
                ax.grid(True, color='white')
                ax.xaxis.set_major_formatter(formatter)
                ax.tick_params(axis='y', colors='white')
                if i == 0:
                    ax.set_title(f"Archivo: {archivo}", color='white')
                if i == len(columnas_presentes) - 1:
                    ax.set_xlabel("Hora", color='white')
                else:
                    ax.tick_params(labelbottom=False)

            self.canvas.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el archivo:\n{e}")

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)

    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)



    def resizeEvent(self, event):
        self.actualizar_fondo()
        super().resizeEvent(event)

    def volver(self):
        self.hide()
        self.ventana_principal.show()






class NivelLiquido(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Niveles de TANQUES")
        self.setFixedSize(1024, 600)
        self.showFullScreen()
        self.energia = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

###        GPIO.setmode(GPIO.BCM)
###        GPIO.setwarnings(False)

###        self.pin_remoto = 23
###        GPIO.setup(self.pin_remoto, GPIO.OUT)
###        GPIO.output(self.pin_remoto, GPIO.LOW)

        self.timer_remoto = QTimer(self)
        self.timer_remoto.setSingleShot(True)
        self.timer_remoto.timeout.connect(self.tiempo_remoto_terminado)

        self.tanques = []
        self.valores_maximos = [100] * CANT_TANQUES  # inicializado a 100 por defecto
        layout_vertical_central = QVBoxLayout()
        layout_vertical_central.addStretch()

        layout_general = QVBoxLayout()
        layout_general.setSpacing(5)
        layout_general.setContentsMargins(10, 5, 10, 10)
        layout_general.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fila_superior = QHBoxLayout()
        fila_superior.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.barcaza_label = QLabel(NOMBRE_EQUIPO)
        self.barcaza_label.setStyleSheet("font-size: 24px; font-weight: bold; color: yellow;")
        fila_superior.addWidget(self.barcaza_label, alignment=Qt.AlignmentFlag.AlignLeft)

        fila_superior.addStretch()

        self.reloj_label = QLabel()
        self.reloj_label.setStyleSheet("font-size: 28px; font-weight: bold;color: white;")
        fila_superior.addWidget(self.reloj_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout_general.addLayout(fila_superior)
        layout_general.addSpacing(30)  # Espacio entre El titulo y fecha y hora y las barras
        self.layout_tanques = QHBoxLayout()
        self.layout_tanques.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(CANT_TANQUES):
            nombre = NOMBRES_TANQUES[i]
            tanque = TanqueWidget(nombre)
            self.layout_tanques.addWidget(tanque)
            self.tanques.append(tanque)
        layout_general.addLayout(self.layout_tanques)

        layout_botones = QHBoxLayout()
        layout_botones.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_general.addSpacing(30)  # Espacio entre barras y botones
        botones = [
            ("CONFIGURACION", self.pedir_clave),
            ("ENERGIA", self.ir_a_energia),
            ("HISTORICO", self.ir_a_historico),
            ("REMOTO ON", self.remoto_on),
            ("REMOTO OFF", self.remoto_off),
            ("RESET SENSORES", lambda: self.ejecutar_script("/var/opt/release/reset-sensores.sh")),
            ("WIFI_ON", self.habilitar_redes),
            ("WIFI_OFF", self.deshabilitar_redes),
        ]

        for texto, funcion in botones:
            boton = QPushButton(texto)
            boton.setStyleSheet("font-size: 16px; font-weight: bold;")
            boton.clicked.connect(funcion)
            layout_botones.addWidget(boton)

        layout_general.addLayout(layout_botones)
        layout_vertical_central.addLayout(layout_general)
        layout_vertical_central.addStretch()

        # Etiqueta de versión abajo a la derecha
        etiqueta_version = QLabel(VERSION)
        etiqueta_version.setStyleSheet("font-size: 12px; color: white;")
        etiqueta_version.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout_general.addWidget(etiqueta_version, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout_vertical_central)
        self.actualizar_fondo()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.actualizar_hora)
        self.timer.start(1000)  #timer que actualiza la hora
        self.actualizar_hora()

        self.timer_csv = QTimer(self)
        self.timer_csv.timeout.connect(self.leer_datos_csv)
        self.timer_csv.start(TIEMPO_REFRESCO_PANTALLA_PPAL)    #timer que actualiza los datos de barras, cantidda y porcentaje
        #self.timer_csv.start(15000)    #timer que actualiza los datos de barras, cantidda y porcentaje
        self.leer_datos_csv()

        self.actualizar_fondo()

    #def actualizar_fondo(self):
    #    fondo = QPixmap("background.jpg").scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    #    palette = QPalette()
    #    palette.setBrush(QPalette.ColorRole.Window, QBrush(fondo))
    #    self.setPalette(palette)

    def actualizar_fondo(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setAutoFillBackground(True)
        self.setPalette(palette)



    def resizeEvent(self, event):
        self.actualizar_fondo()
        super().resizeEvent(event)

    def actualizar_hora(self):
        hora = QDateTime.currentDateTime().toString("dd/MM/yyyy HH:mm:ss")
        self.reloj_label.setText(hora)

    def ir_a_energia(self):
        if not hasattr(self, 'energia') or self.energia is None:
            self.energia = Energia(self)
        self.energia.showFullScreen()
        self.hide()

    def remoto_on(self):
        dialogo = DialogoClave(CLAVE_BOTONES, self)
        if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.clave_valida:
 ###           GPIO.output(self.pin_remoto, GPIO.HIGH)
            #lambda: self.ejecutar_script("/var/opt/mremoto/mremoto-on.sh")
            self.ejecutar_script("/var/opt/mremoto/mremoto-on.sh")
            self.timer_remoto.start(3600 * 1000)  # 1 hora
            QMessageBox.information(self, "Remoto", "Salida activada por 1 hora.")

    def remoto_off(self):
        self.apagar_remoto_pin()


    def tiempo_remoto_terminado(self):
        dialogo = MensajeTimeout(self)
        dialogo.exec()

        if dialogo.seleccion == 'extender':
            self.timer_remoto.start(3600 * 1000)
            QMessageBox.information(self, "Extensión", "Se extendió por una hora más.")
        else:
            self.apagar_remoto_pin()

    def apagar_remoto_pin(self):
####        GPIO.output(self.pin_remoto, GPIO.LOW)
        #lambda: self.ejecutar_script("/var/opt/mremoto/mremoto-off.sh")
        self.ejecutar_script("/var/opt/mremoto/mremoto-off.sh")
        print("apago pin")
        self.timer_remoto.stop()


    def ir_a_historico(self):
        if not hasattr(self, 'historico') or self.historico is None:
            if Tipo_Visualizacion== True:
                self.historico = Historico(self)
            else:
                self.historico = Historico_Canales(self)
        self.historico.showFullScreen()
        self.hide()

    def pedir_clave(self):
        dialogo = DialogoClave(CLAVE_CORRECTA, self)
        if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.clave_valida:
            self.ir_a_configuracion()

    def ir_a_configuracion(self):
        if not hasattr(self, 'configuracion') or self.configuracion is None:
            self.configuracion = Configuracion(self)
        self.configuracion.showFullScreen()  
        self.hide()

    def habilitar_redes(self):
        try:
            dialogo = DialogoClave(CLAVE_BOTONES, self)
            if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.clave_valida:
                # Ejecutar comandos para habilitar Wi-Fi y Bluetooth
                subprocess.run(["sudo", "rfkill", "unblock", "wifi"], check=True)
                subprocess.run(["sudo", "rfkill", "unblock", "bluetooth"], check=True)
                QMessageBox.information(self, "Éxito", "Wi-Fi y Bluetooth habilitados correctamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al habilitar Wi-Fi y Bluetooth\n{e}")

    def deshabilitar_redes(self):
        try:
            # Ejecutar comandos para habilitar Wi-Fi y Bluetooth
            subprocess.run(["sudo", "rfkill", "block", "wifi"], check=True)
            subprocess.run(["sudo", "rfkill", "block", "bluetooth"], check=True)
            QMessageBox.information(self, "Éxito", "Wi-Fi y Bluetooth deshabilitados correctamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al deshabilitar Wi-Fi y Bluetooth\n{e}")

    def ejecutar_script(self, script_path):
        try:
            # Ejecutar el script proporcionado
            subprocess.run(["bash", script_path], check=True)

            # Mostrar mensaje de éxito
            QMessageBox.information(self, "Éxito", f"El script {script_path} se ejecutó correctamente.")
        except subprocess.CalledProcessError as e:
            # Manejar errores si el script falla
            QMessageBox.critical(self, "Error", f"Error al ejecutar el script {script_path}:\n{e}")
        except Exception as e:
            # Manejar cualquier otro error
            QMessageBox.critical(self, "Error", f"Error inesperado al ejecutar el script {script_path}:\n{e}")


    def leerDatoTanqueDBSQLite(self,DATO):
        import sqlite3
        database_file = RUTA_DB
        conn = sqlite3.connect(database_file)
        cursor = conn.cursor()
        CONSULTA = 'SELECT var_valor FROM tanques WHERE var_name==' + "'" + DATO + "'" + ";"
        cursor.execute(CONSULTA)
        rows = cursor.fetchall()
        for row in rows:       
            X = row[0]
        return X
        conn.close()



    def leer_datos_csv(self):
        try:
            with open(ARCHIVO_CALIBRACION_CSV, newline='') as csvfile2:
                lector2 = csv.reader(csvfile2, delimiter=';') #defino delimitador como ;
                next(lector2, None)  # Saltar la cabecera
                alturas = next(lector2, [])

                if len(alturas) >= CANT_TANQUES:
                    for i in range(CANT_TANQUES):
                        try:
                            valor_dato = int(self.leerDatoTanqueDBSQLite(f"SONDEO_T{i+1}"))
                         
                            valor_maximo = int(alturas[i])
                            self.valores_maximos[i] = valor_maximo

                            self.tanques[i].barra.setMaximum(valor_maximo)

                            resultado = valor_dato
                            resultado = max(0, min(valor_maximo, resultado))

                            porcentaje = (resultado / valor_maximo) * 100 if valor_maximo > 0 else 0

                            self.tanques[i].actualizar_valores(resultado, porcentaje)
                                                      
                        except ValueError:
                            self.tanques[i].actualizar_valores(0)
                            
        except Exception as e:
            print(f"Error al leer los archivos CSV: {e}")


class MensajeTimeout(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tiempo finalizado")
        self.setModal(True)

        self.seleccion = None  # 'extender' o 'apagar'

        layout = QVBoxLayout()
        etiqueta = QLabel("¿Desea extender el tiempo de REMOTO por otra hora?")
        etiqueta.setStyleSheet("font-size: 18px;")
        layout.addWidget(etiqueta)

         # Etiqueta de cuenta regresiva
        self.label_cuenta_regresiva = QLabel("Tiempo restante: 60 segundos")
        self.label_cuenta_regresiva.setStyleSheet("font-size: 16px; color: red;")
        layout.addWidget(self.label_cuenta_regresiva)

        botones_layout = QHBoxLayout()
        boton_extender = QPushButton("Extender")
        boton_apagar = QPushButton("Apagar")

        boton_extender.clicked.connect(self.elegir_extender)
        boton_apagar.clicked.connect(self.elegir_apagar)

        botones_layout.addWidget(boton_extender)
        botones_layout.addWidget(boton_apagar)
        layout.addLayout(botones_layout)

        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timeout_apagar)
        self.timer.start(60000)  # 60 segundos

    def elegir_extender(self):
        self.seleccion = 'extender'
        self.accept()

    def elegir_apagar(self):
        self.seleccion = 'apagar'
        self.accept()

    def timeout_apagar(self):
        self.seleccion = 'apagar'
        self.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QLabel {
            color: black;
            font-weight: bold;
        }

        QLineEdit {
            background-color: #222;
            color: white;
            border: 1px solid white;
        }
        QPushButton {
            background-color: #333;
            color: white;
            border: 1px solid white;
            padding: 5px;
            min-height: 36px;         /* altura boton */
            border-radius: 10px;      /* bordes redondeados del boton*/

        }
        QPushButton:hover {
            background-color: #555;
        }
        QProgressBar {
            border: 2px solid white;
            border-radius: 5px;
            background: #111;
            color: transparent;
        }
         QProgressBar::chunk {
                background-color: #4CAF50;
                margin: 1px;
            }

    """)

    ventana = NivelLiquido()
    if FULL_SCREEN==False:
        ventana.show()  #Para desarrollar
    else:
        ventana.showFullScreen()  #Full screen

    sys.exit(app.exec())


    
