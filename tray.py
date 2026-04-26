import sqlite3
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import webbrowser
import os
import threading
import subprocess
from datetime import date

# --- 1. ФУНКЦІЯ ІНТЕРАКТИВНОГО СПОВІЩЕННЯ ---
def macos_notify(title, message):
    """Виводить вікно з кнопками та обробляє натискання"""
    # AppleScript для створення вікна з двома кнопками
    # button 2 ("Відкрити") встановлена як default (синя кнопка)
    applescript = f'''
    set theResult to display alert "{title}" message "{message}" buttons {{"Закрити", "Відкрити"}} default button 2
    return button returned of theResult
    '''
    
    try:
        # Виконуємо скрипт та отримуємо назву натиснутої кнопки
        result = subprocess.check_output(['osascript', '-e', applescript], text=True).strip()
        
        if result == "Відкрити":
            print("🚀 Перехід до панелі керування...")
            webbrowser.open("http://localhost:8501")
        else:
            print("✅ Вікно закрито користувачем.")
            
    except Exception as e:
        print(f"❌ Помилка відображення вікна: {e}")

# --- 2. РОБОТА З БАЗОЮ ---
def get_urgent_count():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "documents.db")
        
        if not os.path.exists(db_path):
            return -1

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SQL запит: рахуємо не закриті документи з дедлайном через 3 дні або менше
        cursor.execute("""
            SELECT COUNT(*) FROM documents 
            WHERE status != 'Виконано' 
            AND (julianday(deadline) - julianday(?)) <= 3
        """, (date.today(),))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"❌ Помилка БД: {e}")
        return 0

# --- 3. ФУНКЦІЇ МЕНЮ ---
def check_now(icon, item):
    print("\n🔘 Перевірка бази даних...")
    count = get_urgent_count()
    
    if count == -1:
        macos_notify("Помилка системи", "Файл бази даних 'documents.db' не знайдено.")
    elif count > 0:
        macos_notify("Термінові завдання", f"Знайдено {count} документів, термін яких добігає кінця. Бажаєте переглянути деталі?")
    else:
        # Якщо все добре, просто виводимо тихе сповіщення (банер), щоб не дратувати вікнами
        os.system(f'osascript -e "display notification \'Всі дедлайни під контролем!\' with title \'ERP: Статус документів\'"')

def open_app(icon, item):
    webbrowser.open("http://localhost:8501")

def exit_action(icon, item):
    print("👋 Програма завершена.")
    icon.stop()

# --- 4. НАЛАШТУВАННЯ ІКОНКИ ТА ЗАПУСК ---
def create_image(width, height):
    # Малюємо синю іконку з білим колом
    image = Image.new('RGB', (width, height), (0, 122, 255))
    dc = ImageDraw.Draw(image)
    dc.ellipse((width//4, height//4, width*3//4, height*3//4), fill=(255, 255, 255))
    return image

# Створюємо меню трею
icon = Icon("ERP_Control", create_image(64, 64), menu=Menu(
    MenuItem("Відкрити панель (Web)", open_app),
    MenuItem("Перевірити терміни зараз", check_now),
    MenuItem("Вихід", exit_action)
))

if __name__ == "__main__":
    print("🚀 Трей-агент запущено. Шукайте іконку в менюбарі Mac (зверху).")
    # Запускаємо іконку (це заблокує основний потік)
    icon.run()