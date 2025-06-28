import os

def print_filenames_in_folder(folder_path):
    try:
        # List all files and directories in the specified folder
        files_and_dirs = os.listdir(folder_path)
        items = {}
        # Iterate over the list and print only files
        for item in files_and_dirs:
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                items[item.split(".")[0]] = (item.split(".")[0] + ".png", item)
                
        print(items)
    
    except FileNotFoundError:
        print(f"Error: The folder '{folder_path}' does not exist.")
    except PermissionError:
        print(f"Error: Permission denied to access the folder '{folder_path}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
folder_path = r'C:\projects\bot\logosmart\bot\assets\tovush_audios'
print_filenames_in_folder(folder_path)
