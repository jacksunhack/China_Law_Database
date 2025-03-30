# split_large_file.py (place in the root project folder)
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# !!! IMPORTANT: Set this path to the large file you want to split !!!
# This is likely the merged output of text files, if you create one.
# If you don't merge text files, this script might not be needed.
INPUT_FILE = "path/to/your/large_merged_output.txt" # <<< CHANGE THIS
# ---

OUTPUT_DIR = "output_parts" # Directory to save the split files
CHUNK_SIZE_MB = 8 # Desired approximate size of each part in Megabytes
CHUNK_SIZE = CHUNK_SIZE_MB * 1024 * 1024  # Size in bytes


def split_file(input_file, output_dir, chunk_size):
    """Splits a large text file into smaller chunks based on size."""
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: '{input_file}'. Please set the INPUT_FILE variable correctly.")
        return
    if not os.path.isfile(input_file):
        logging.error(f"Input path is not a file: '{input_file}'.")
        return

    try:
        file_size = os.path.getsize(input_file)
        logging.info(f"Input file: '{input_file}' ({file_size / (1024*1024):.2f} MB)")
        logging.info(f"Target chunk size: {chunk_size / (1024*1024):.2f} MB")
    except OSError as e:
        logging.error(f"Could not get size of input file '{input_file}': {e}")
        return

    os.makedirs(output_dir, exist_ok=True)
    # Create a base name for output files (e.g., large_merged_output_part1.txt)
    base_filename = os.path.splitext(os.path.basename(input_file))[0]

    part_num = 1
    current_size = 0
    current_file = None
    output_file_path = None
    lines_in_part = 0

    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            for line in infile:
                line_bytes = line.encode('utf-8') # Calculate size in bytes
                line_size = len(line_bytes)

                # Start a new file if:
                # 1. It's the very first line (current_file is None)
                # 2. Adding the current line exceeds chunk_size AND the current part has content
                if current_file is None or (current_size + line_size > chunk_size and current_size > 0):
                    if current_file:
                        current_file.close()
                        logging.info(f"Finished writing part {part_num - 1}: '{os.path.basename(output_file_path)}' ({current_size / (1024*1024):.2f} MB, {lines_in_part} lines)")

                    output_file_path = os.path.join(output_dir, f"{base_filename}_part{part_num}.txt")
                    # Open new file for writing
                    current_file = open(output_file_path, 'w', encoding='utf-8')
                    logging.info(f"Creating new part {part_num}: '{os.path.basename(output_file_path)}'")
                    part_num += 1
                    current_size = 0 # Reset size for the new part
                    lines_in_part = 0 # Reset line count for the new part

                # Write the line to the current part file
                current_file.write(line)
                current_size += line_size
                lines_in_part += 1

            # Close the last file after the loop finishes
            if current_file:
                current_file.close()
                logging.info(f"Finished writing last part {part_num - 1}: '{os.path.basename(output_file_path)}' ({current_size / (1024*1024):.2f} MB, {lines_in_part} lines)")

        logging.info(f"File '{input_file}' successfully split into {part_num - 1} parts in directory: '{output_dir}'")

    except IOError as e:
        logging.error(f"Error reading input file '{input_file}' or writing to output: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during splitting: {e}")
        # Clean up potentially open file handle if an error occurred mid-write
        if current_file and not current_file.closed:
             try:
                 current_file.close()
                 logging.warning("Closed output file handle after error.")
             except Exception as close_err:
                 logging.error(f"Error closing file handle after error: {close_err}")

if __name__ == "__main__":
    if INPUT_FILE == "path/to/your/large_merged_output.txt":
         logging.error("Please edit 'split_large_file.py' and set the INPUT_FILE variable before running.")
    else:
         split_file(INPUT_FILE, OUTPUT_DIR, CHUNK_SIZE)