# Assets para Mascota Lip-Sync

Este directorio contiene las imágenes de la mascota utilizadas para la animación de sincronización de labios (lip-sync). El sistema utiliza el estándar de **Rhubarb Lip Sync** para alternar la imagen del personaje según el sonido detectado en el audio.

---

## 1. Convención de Nombres de Archivos

Debes colocar las siguientes imágenes en esta carpeta (`assets/mascota/`). Los nombres deben coincidir con la configuración definida en `config.yaml` para el nicho `mascota_tutorial`:

| Cue Rhubarb | Fonemas Asociados | Descripción de la Boca | Nombre de Archivo Recomendado |
|-------------|-------------------|-------------------------|-------------------------------|
| **A**       | /p/, /b/, /m/     | Labios cerrados         | `mouth_A.png` (o placeholder) |
| **B**       | /t/, /d/, /k/, /g/| Dientes expuestos, boca ligeramente abierta | `mouth_B.png` |
| **C**       | /e/, /i/          | Sonrisa leve            | `mouth_C.png` |
| **D**       | /a/               | Boca completamente abierta | `mouth_D.png` |
| **E**       | /o/               | Labios redondeados      | `mouth_E.png` |
| **F**       | /u/               | Labios fruncidos        | `mouth_F.png` |
| **X**       | (silencio)        | Boca en reposo          | `mouth_X.png` |

*Nota: Si tienes menos imágenes (por ejemplo, 5), puedes reutilizar el mismo archivo para múltiples cues (ej. mapear E a D, y F a B, y X a A) editando el mapeo en `config.yaml`.*

---

## 2. Recomendaciones de Formato y Tamaño

- **Transparencia:** Se recomienda usar formato **PNG con canal Alpha (transparente)** para que el títere pueda superponerse limpiamente en el video final si es necesario (el pipeline normaliza estas imágenes centrándolas de manera proporcional en el ratio del video).
- **Consistencia:** Todas las imágenes deben tener exactamente el mismo encuadre, pose, iluminación y dimensiones (ej. 1080x1920 si es vertical nativo, o cuadradas como 1000x1000). Solo debe cambiar la zona de la boca.

---

## 3. Instalación de Rhubarb Lip Sync

El pipeline asume que tienes el binario ejecutable de Rhubarb:

1. Descarga el release correspondiente a tu sistema operativo desde:
   👉 [Rhubarb Lip Sync Releases](https://github.com/DanielSWolf/rhubarb-lip-sync/releases)
2. Extrae el contenido y coloca el binario (`rhubarb.exe` en Windows o `rhubarb` en Linux/Mac) en:
   - Una carpeta `bin/` dentro de la raíz de este proyecto (ej: `bin/rhubarb.exe`), **O**
   - Agrega la carpeta de Rhubarb a la variable de entorno `PATH` de tu sistema.
