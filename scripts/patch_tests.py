import glob

for test_file in glob.glob("tests/*.py"):
    with open(test_file, 'r') as f:
        content = f.read()
    
    if "AppTest.from_file(" in content:
        # We need to inject the mock session state right after the AppTest instantiation.
        # It could be named 'at' or 'at_map' etc.
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if "AppTest.from_file" in line and not "test_auth_security.py" in test_file:
                # Extract the variable name
                var_name = line.split("=")[0].strip()
                # Determine indentation
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + f'{var_name}.session_state["authentication_status"] = True')
                new_lines.append(" " * indent + f'{var_name}.session_state["user_role"] = "Commander"')
        
        with open(test_file, 'w') as f:
            f.write('\n'.join(new_lines))
            
print("Auth mocks injected into tests.")
