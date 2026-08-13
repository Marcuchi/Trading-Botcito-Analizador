"""Base comun para los indicadores.

Cada indicador vive en su propio archivo dentro de este paquete y debe:
  - heredar de Indicador
  - definir su `nombre`
  - implementar `compute(df)` devolviendo un dict serializable con sus resultados
  - implementar `render(resultado)` para imprimir su reporte
  - implementar `mensaje(resultado, header=None)` con el texto de notificacion
"""


class Indicador:
    nombre = "base"

    def compute(self, df):
        raise NotImplementedError

    def render(self, resultado):
        print(self.mensaje(resultado))

    def mensaje(self, resultado, header=None):
        head = f"{header}\n" if header else ""
        return f"{head}{self.nombre}: {resultado}"
