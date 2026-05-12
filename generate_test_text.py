import os

def generate_test_file(filename="test.txt"):
    # z ksiazki przelaskowskiego, 
    pattern1 = "INNYCH KOMPRESJA_DANYCH_TO_PRZEDMIOT_O_ KOMPRESJI_PRZEDE WSZYSTKIM_WYBRA "
    pattern2 = "BOBAS_BOBEK_BOBCIO "
    
    
    content = pattern1 * 100
    content += "A" * 500  
    content += pattern2 * 200
    content += pattern1 * 50

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
        
    size = os.path.getsize(filename)
    print(f" Test file created: {filename}")
    print(f" Test file size: {size} bytes.")

if __name__ == "__main__":
    generate_test_file()