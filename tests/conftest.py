"""Configuration pytest commune."""
import os
import tempfile

# Isole les journaux des tests du dossier utilisateur.
os.environ.setdefault("ZTVD_LOG_DIR", tempfile.mkdtemp(prefix="ztvd-pro-tests-"))
# Permet d'instancier des widgets Qt sans serveur graphique.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
