import unittest

texto_txt = """
Título del Proyecto
Ejemplo de un archivo en formato texto plano.
"""

def create_text(name, text):
    """ crea el archivo de texto plano
        recibe el nombre de archivo y un texto
    """
    try:
        with open(f"app\models\{name}.txt", "w", encoding="utf-8") as archivo:
            archivo.write(text)
        print(f'El archivo {name}.txt ah sido creado.')

    except FileNotFoundError:
        print(f'Error: La ruta {name}.txt no ah sido encontrada.')

create_text('prueba', texto_txt)

