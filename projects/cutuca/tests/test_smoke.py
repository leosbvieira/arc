"""Import-safety: the package (including app wiring) must import with zero heavy
deps installed (telegram, apscheduler, anthropic, requests all lazy)."""


def test_package_imports():
    import cutuca  # noqa: F401
    import cutuca.app  # noqa: F401
    import cutuca.capture  # noqa: F401
    import cutuca.clickup  # noqa: F401
    import cutuca.nudge  # noqa: F401
    import cutuca.parser  # noqa: F401
    import cutuca.telegram_channel  # noqa: F401
    from cutuca.__main__ import main  # noqa: F401


def test_main_unknown_command_returns_2():
    from cutuca.__main__ import main

    assert main(["nope"]) == 2
