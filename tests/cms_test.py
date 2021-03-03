def test_import():
    from sovon_cms import main
    print('version:', main.__version__)


def test_toolbox():
    from tabular_toolbox import __version__
    print('tabular_toolbox', __version__)
