import os
import subprocess

def manage_firewall(folder_path, action):
    if not os.path.exists(folder_path):
        print(f"--- Error: The path '{folder_path}' does not exist. ---")
        return

    ext = ".exe"
    count = 0
    
    # Walk through the folder and subfolders
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(ext):
                full_path = os.path.join(root, file)
                # We use a unique prefix so we can target these rules specifically later
                rule_name = f"Block_Folder_{file}"
                
                if action == "block":
                    cmd = (f'netsh advfirewall firewall add rule name="{rule_name}" '
                           f'dir=out program="{full_path}" action=block')
                    verb = "Blocked"
                else:
                    # Unblock removes the rule by its specific name
                    cmd = f'netsh advfirewall firewall delete rule name="{rule_name}"'
                    verb = "Unblocked/Cleared"

                try:
                    subprocess.run(cmd, shell=True, check=True, capture_output=True)
                    print(f"Successfully {verb}: {file}")
                    count += 1
                except subprocess.CalledProcessError:
                    print(f"Skipped/Failed: {file} (Check Admin rights or if rule exists)")

    print(f"\n--- Task Complete. Processed {count} executable(s). ---")

def main():
    print("=== Windows Folder Internet Firewall Tool ===")
    
    # 1. Ask for the Folder Path
    target_dir = input("Enter the full path of the folder: ").strip().strip('"')
    
    # 2. Ask for the Action
    print("\nWhat would you like to do?")
    print("1. Block all .exe files in this folder")
    print("2. Unblock (Remove rules) for this folder")
    choice = input("Select (1/2): ")

    if choice == '1':
        manage_firewall(target_dir, "block")
    elif choice == '2':
        manage_firewall(target_dir, "unblock")
    else:
        print("Invalid selection. Exiting.")

if __name__ == "__main__":
    main()