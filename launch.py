from tools.loader import Loader
from tools.single_app import SingleApp

if __name__ == "__main__":
    config = Loader("config.yaml").load()

    with SingleApp(config.title) as app:
        if not app.is_running():
            from tools import img_to64
            from tools.widgets import Splash

            img = img_to64("icons/ok.ico", height=config.UI.logo_height)
            with Splash(img):
                # loooong import
                from tctg import TCTGWindow

                window = TCTGWindow(app, config)
            window.loop()

    print("Exit")
