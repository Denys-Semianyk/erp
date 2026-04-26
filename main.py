import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# --- 1. НАЛАШТУВАННЯ ТА БАЗА ДАНИХ ---
st.set_page_config(page_title="ERP Документообіг v2.0", layout="wide")

def get_connection():
    return sqlite3.connect("documents.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Таблиця документів
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            doc_number TEXT,
            description TEXT,
            responsible_person TEXT,
            deadline DATE,
            status TEXT DEFAULT 'В роботі'
        )
    ''')
    # Таблиця шаблонів
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            default_type TEXT,
            default_desc TEXT
        )
    ''')
    
    # Додаємо базові шаблони, якщо таблиця порожня
    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0:
        base_templates = [
            ("Щомісячний звіт", "Наказ", "Підготовка та подання статистичного звіту за минулий місяць."),
            ("Оплата рахунку", "Рахунок", "Погодження та оплата послуг згідно з договором."),
            ("Інструктаж з ОП", "Наказ", "Проведення планового інструктажу з охорони праці."),
            ("Інвентаризація", "Угода", "Перевірка залишків товарно-матеріальних цінностей на складі.")
        ]
        cursor.executemany("INSERT INTO templates (title, default_type, default_desc) VALUES (?,?,?)", base_templates)
    
    conn.commit()
    conn.close()

init_db()

# --- 2. ФУНКЦІЇ КЕРУВАННЯ ---
def update_status(doc_id, new_status):
    conn = get_connection()
    curr = conn.cursor()
    curr.execute("UPDATE documents SET status = ? WHERE id = ?", (new_status, doc_id))
    conn.commit()
    conn.close()

def delete_doc(doc_id):
    conn = get_connection()
    curr = conn.cursor()
    curr.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

# --- 3. ІНТЕРФЕЙС ТА БІЧНА ПАНЕЛЬ ---
st.title("Система моніторингу документів")

with st.sidebar:
    st.header("Швидке заповнення")
    
    # Отримуємо шаблони для вибору
    conn = get_connection()
    tpl_df = pd.read_sql_query("SELECT * FROM templates", conn)
    conn.close()
    
    selected_template = st.selectbox("Оберіть шаблон:", ["Свій варіант"] + tpl_df['title'].tolist())
    
    # Визначаємо початкові значення на основі шаблону
    if selected_template != "Свій варіант":
        tpl_data = tpl_df[tpl_df['title'] == selected_template].iloc[0]
        init_type = tpl_data['default_type']
        init_desc = tpl_data['default_desc']
    else:
        init_type = "Наказ"
        init_desc = ""

    st.divider()
    st.header("➕ Новий запис")
    
    with st.form("add_form", clear_on_submit=True):
        # Поля автоматично заповнюються з шаблону
        d_type_list = ["Наказ", "Договір", "Угода", "Рахунок"]
        doc_type = st.selectbox("Тип", d_type_list, index=d_type_list.index(init_type))
        
        number = st.text_input("№ документа", placeholder="Напр. №123-А")
        main_desc = st.text_area("Зміст", value=init_desc)
        
        st.write("**Список розсилки (повідомити):**")
        col_ch1, col_ch2 = st.columns(2)
        notify_acc = col_ch1.checkbox("Бухгалтерія")
        notify_hr = col_ch1.checkbox("Кадри")
        notify_dir = col_ch2.checkbox("Дирекція")
        notify_wh = col_ch2.checkbox("Склад")
        
        resp = st.text_input("Відповідальний")
        dline = st.date_input("Термін виконання", date.today())
        
        if st.form_submit_button("Зберегти до бази"):
            # Збираємо список розсилки в текст
            notifications = []
            if notify_acc: notifications.append("Бухгалтерія")
            if notify_hr: notifications.append("Кадри")
            if notify_dir: notifications.append("Дирекція")
            if notify_wh: notifications.append("Склад")
            
            full_desc = main_desc
            if notifications:
                full_desc += "\n📌 Повідомити: " + ", ".join(notifications)
            
            conn = get_connection()
            curr = conn.cursor()
            curr.execute("""
                INSERT INTO documents (doc_type, doc_number, description, responsible_person, deadline) 
                VALUES (?, ?, ?, ?, ?)
            """, (doc_type, number, full_desc, resp, dline))
            conn.commit()
            conn.close()
            st.success("Додано успішно!")
            st.rerun()

# --- 4. ОСНОВНИЙ КОНТЕНТ ---
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM documents", conn)
conn.close()

if not df.empty:
    # Аналітика
    df['deadline'] = pd.to_datetime(df['deadline'])
    df['Днів залишилось'] = (df['deadline'].dt.date - date.today()).apply(lambda x: x.days)

    m1, m2, m3 = st.columns(3)
    m1.metric("Документів", len(df))
    urgent = len(df[(df['Днів залишилось'] <= 3) & (df['status'] != 'Виконано')])
    m2.metric("Критичні (≤3 дні)", urgent, delta_color="inverse")
    m3.metric("Завершено", len(df[df['status'] == 'Виконано']))

    st.write("### Реєстр завдань")
    
    # Експорт
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("Завантажити звіт CSV", csv, f"report_{date.today()}.csv", "text/csv")

    # Підсвітка
    def style_rows(row):
        if row['status'] == 'Виконано':
            return ['background-color: rgba(0, 255, 0, 0.05); color: gray'] * len(row)
        if row['Днів залишилось'] <= 3:
            return ['background-color: rgba(255, 75, 75, 0.2)'] * len(row)
        return [''] * len(row)

    st.dataframe(df.style.apply(style_rows, axis=1), use_container_width=True, hide_index=True)

    st.divider()

    # --- КЕРУВАННЯ ---
    st.subheader("Швидкі дії")
    c_sel, c_btn = st.columns([1, 2])
    
    with c_sel:
        target_id = st.selectbox("ID для редагування:", df['id'].tolist())
    
    with c_btn:
        b1, b2, b3 = st.columns(3)
        if b1.button("Виконано", use_container_width=True):
            update_status(target_id, "Виконано")
            st.rerun()
        if b2.button("🔄 В роботу", use_container_width=True):
            update_status(target_id, "В роботі")
            st.rerun()
        if b3.button("Видалити", use_container_width=True):
            delete_doc(target_id)
            st.rerun()
else:
    st.info("Реєстр порожній. Скористайтеся шаблонами зліва.")