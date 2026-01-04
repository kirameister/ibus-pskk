# justfile

# Variables
venv_path := "/opt/ibus-pskk/venv"
install_root := "/opt/ibus-pskk"
ibus_component_dir := "/usr/share/ibus/component"
gschema_dir := "/usr/share/glib-2.0/schemas"
icon_dir := "/usr/local/share/icons/hicolor"


# Default recipe (runs when you just type 'just')
default:
    @just --list

# Create virtual environment
create-venv:
    python3 -m venv --system-site-packages {{venv_path}}

# Install Python dependencies
install-deps: create-venv
    {{venv_path}}/bin/pip install --upgrade pip
    {{venv_path}}/bin/pip install -r requirements.txt

# Compile and install GSettings schema
install-schema:
    mkdir -p {{gschema_dir}}
    cp data/org.freedesktop.ibus.engine.pskk.gschema.xml {{gschema_dir}}/
    glib-compile-schemas {{gschema_dir}}

# Install ICON
install-icons:
    mkdir -p {{icon_dir}}/scalable/apps
    cp data/icons/ibus-pskk.svg {{icon_dir}}/scalable/apps/
    chmod 644 {{icon_dir}}/scalable/apps/ibus-pskk.svg
    gtk-update-icon-cache {{icon_dir}} || true

# Install IME files and data
install-files:
    mkdir -p {{install_root}}/models
    mkdir -p {{install_root}}/lib
    cp -r src/* {{install_root}}/lib/
    #cp -r models/* {{install_root}}/models/ ## FIXME
    cp data/pskk.xml {{ibus_component_dir}}/
    chmod 644 {{ibus_component_dir}}/pskk.xml

# Full installation
install: install-deps install-files install-schema install-icons
    chmod 755 {{install_root}}/lib/*
    @echo "Installation complete!"
    @echo "Run 'ibus restart' to activate the IME"

# Development installation (uses local venv)
dev-install:
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    #./venv/bin/pip install -e .

# Uninstall
uninstall:
    rm -rf {{install_root}}
    rm -f {{ibus_component_dir}}/pskk.xml
    rm -f {{gschema_dir}}/org.freedesktop.ibus.engine.pskk.gschema.xml
    glib-compile-schemas {{gschema_dir}}
    rm -f {{icon_dir}}/scalable/apps/ibus-pskk.svg
    gtk-update-icon-cache {{icon_dir}} || true
    @echo "Uninstalled. Run 'ibus restart'"

# Restart IBus
restart-ibus:
    ibus restart

# Clean development files
clean:
    rm -rf venv
    rm -rf build dist *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} +

# Run tests
test:
    ./venv/bin/pytest tests/

## Project Structure
### 
### your-ime/
### ├── justfile
### ├── requirements.txt
### ├── setup.py (optional)
### ├── src/
### │   ├── __init__.py
### │   ├── main.py (IBus engine entry point)
### │   ├── engine.py
### │   └── converter.py
### ├── models/
### │   └── crf_model.pkl
### ├── data/
### │   └── ibus-your-ime.xml
### └── tests/
###     └── test_converter.py
