# load the plugin for local test runs without installing the package
# When installed as a package, the plugin is auto-loaded via entry_points
try:
    import monocle_test_tools
except ImportError:
    pytest_plugins = ["monocle_test_tools.pytest_plugin"]
