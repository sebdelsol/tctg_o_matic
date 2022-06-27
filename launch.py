from tools.loader import Loader
from tools.single_app import SingleApp

CONFIG = "config.yaml"
LOGO = "icons/logo.ico"

if __name__ == "__main__":
    config = Loader(CONFIG).load()

    with SingleApp(config.title) as app:
        if app.can_run:
            from tools import img_to64
            from tools.widgets import Splash

            with Splash(img_to64(LOGO, height=config.UI.logo_height)):
                # loooong import
                from tctg import TCTGWindow

                window = TCTGWindow(app, config)
            window.loop()
