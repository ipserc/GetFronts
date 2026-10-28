"""Autoría de GetFronts: lo que muestran ``--about`` (inglés) y ``--acerca-de`` (español)."""

from __future__ import annotations

from getfronts.version import full_version

PROJECT_URL = "https://github.com/ipserc/GetFronts"

ABOUT = {
    "en": """\
Author: Ipserc & Claude
Email: ipserc at selenitas dot es
Conception date: 2026.10.27
Motivation: I love seeing album covers on my music player.
Acknowledgments: Thanks to Linux. Thanks to the FSF. Thanks to Python.
Thanks to those who contribute selflessly to the world of software.
Thank you.""",
    "es": """\
Autores: Ipserc & Claude
Email: ipserc at selenitas dot es
Fecha de concepción: 2026.10.27
Motivación: me encanta ver las carátulas de los álbumes en mi reproductor musical.
Agradecimientos: gracias a Linux, gracias a la FSF, gracias a Python.
Gracias a quienes contribuyen desinteresadamente al mundo del software.
Gracias.""",
}


def about_text(lang: str) -> str:
    """Versión, autoría y enlace al proyecto en el idioma pedido (``en`` o ``es``)."""
    return f"GetFronts {full_version()}\n\n{ABOUT[lang]}\n\n{PROJECT_URL}"
