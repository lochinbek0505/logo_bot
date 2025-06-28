import os


def rename_files_to_lowercase(directory):
    for filename in os.listdir(directory):
        lowercase_filename = filename.lower()
        if filename != lowercase_filename:
            os.rename(
                os.path.join(directory, filename),
                os.path.join(directory, lowercase_filename),
            )


# Usage
directory = "bot/assets/hayvon_imgs"
rename_files_to_lowercase(directory)
