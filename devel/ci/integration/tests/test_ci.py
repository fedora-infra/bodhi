def test_ci_error(bodhi_container):
    """Test a CI error"""
    print(bodhi_container.execute("mount"))
    print(bodhi_container.execute("ls -l"))
    print(bodhi_container.execute("ls -l /"))