# ui_manage_history.py
import streamlit as st
from utils import database as db

def render_page(current_user_id, logs):
    st.title("Manage Data History")
    st.write("Verwalten Sie Ihre eingetragenen Zählerstände, filtern Sie historische Daten oder korrigieren Sie Fehlbuchungen.")
    
    if logs.empty:
        st.info("No recorded database entries found.")
        return

    # ---------------------------------------------------------
    # UX-UPGRADE 1: KATEGORIE-FILTER FÜR BESSERE ÜBERSICHT
    # ---------------------------------------------------------
    st.subheader("📊 Verlauf & Filterung")
    
    filter_options = [
        "Alle Einträge anzeigen", 
        "Electricity (kWh)", 
        "Hot Water (MWh)", 
        "Cold Water (m³)"
    ]
    selected_filter = st.selectbox("Historie filtern nach:", filter_options)
    
    # Logs chronologisch absteigend sortieren für die Anzeige
    logs_sorted = logs.sort_values(by=["date", "id"], ascending=[False, False])
    
    if selected_filter != "Alle Einträge anzeigen":
        filtered_logs = logs_sorted[logs_sorted["meter"] == selected_filter]
    else:
        filtered_logs = logs_sorted

    # Tabelle anzeigen
    st.dataframe(
        filtered_logs.drop(columns=["user_id"], errors="ignore").rename(columns={
            "id": "ID",
            "date": "Erfassungsdatum",
            "meter": "Zählerkategorie",
            "reading": "Zählerstand (kumuliert)"
        }), 
        width="stretch"
    )
    
    st.markdown("---")
    
    # ---------------------------------------------------------
    # UX-UPGRADE 2: SICHERES LÖSCHEN PER SELECTION & CONFIRMATION
    # ---------------------------------------------------------
    st.subheader("🗑️ Einträge korrigieren / entfernen")
    st.write("Wählen Sie einen fehlerhaften Eintrag aus der Liste aus, um ihn unwiderruflich zu löschen.")
    
    if filtered_logs.empty:
        st.caption("Keine Einträge im ausgewählten Filter vorhanden.")
        return

    # Optionen für das Dropdown-Menü lesbar formatieren
    delete_options = []
    for _, row in filtered_logs.iterrows():
        delete_options.append({
            "id": row["id"],
            "label": f"ID {row['id']} | {row['date']} | {row['meter']} | Zählerstand: {row['reading']:,.3f}"
        })
        
    # ui_manage_history.py (Korrigierter unterer Abschnitt)
    
    target_record = st.selectbox(
        "Zu löschenden Eintrag auswählen:",
        options=delete_options,
        format_func=lambda x: x["label"] if x else ""
    )
    
    # Sicherheitsabfrage für statische Code-Analyse (Pylance) und Laufzeit-Schutz
    if target_record is not None:
        # Zweistufige Bestätigung via Popover zum Schutz vor Fehlklicks
        with st.popover("🗑️ Löschung bestätigen", width="stretch"):
            st.warning(f"Sind Sie sicher, dass Sie den folgenden Eintrag unwiderruflich löschen möchten?\n\n**{target_record['label']}**")
            
            confirm_delete = st.button(
                "Ja, Eintrag jetzt dauerhaft löschen", 
                type="primary", 
                width="stretch"
            )
            
            if confirm_delete:
                # UX-Spinner & Toast während des Löschvorgangs
                with st.spinner(f"Verbinde mit Cloud-Datenbank... Entferne Eintrag ID {target_record['id']}"):
                    db.execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(target_record["id"])})
                
                # CACHE-BUSTING: Logs und Berechnungen verwerfen
                st.session_state.pop("logs", None)
                st.session_state.pop("processed_logs", None)
                st.session_state.pop("stats", None)
                
                st.toast(f"Eintrag ID {target_record['id']} erfolgreich gelöscht.", icon="🗑️")
                st.rerun()