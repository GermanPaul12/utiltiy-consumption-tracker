# ui/ui_manage_history.py
import streamlit as st
from utils import database as db
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render_page(current_user_id, logs):
    st.title(t("history_title"))
    st.write(t("history_subtitle"))
    
    if logs.empty:
        st.info(t("history_no_entries"))
        return

    # ---------------------------------------------------------
    # HISTORIEN-FILTER (Dynamisch lokalisiert)
    # ---------------------------------------------------------
    st.subheader(t("history_filter_header"))
    
    db_filter_options = ["all", "Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
    
    # Zuordnungstabelle der Übersetzungsschlüssel für die Filter
    option_key_map = {
        "all": "history_option_all",
        "Electricity (kWh)": "log_option_elec",
        "Hot Water (MWh)": "log_option_hw",
        "Cold Water (m³)": "log_option_cw"
    }
    
    translated_filters = [t(option_key_map[item]) for item in db_filter_options]
    selected_filter_trans = st.selectbox(t("history_filter_label"), options=translated_filters)
    
    # Rück-Mapping der Filterschnittstelle auf den internen Datenbank-Schlüssel
    selected_index = translated_filters.index(selected_filter_trans)
    selected_filter = db_filter_options[selected_index]
    
    # Logs chronologisch absteigend sortieren für die Anzeige
    logs_sorted = logs.sort_values(by=["date", "id"], ascending=[False, False])
    
    if selected_filter != "all":
        filtered_logs = logs_sorted[logs_sorted["meter"] == selected_filter]
    else:
        filtered_logs = logs_sorted

    # Tabelle dynamisch lokalisiert anzeigen
    st.dataframe(
        filtered_logs.drop(columns=["user_id"], errors="ignore").rename(columns={
            "id": t("history_col_id"),
            "date": t("history_col_date"),
            "meter": t("history_col_meter"),
            "reading": t("history_col_reading")
        }), 
        width="stretch"
    )
    
    st.markdown("---")
    
    # ---------------------------------------------------------
    # SICHERES LÖSCHEN (Vollständig übersetzt)
    # ---------------------------------------------------------
    st.subheader(t("history_delete_header"))
    st.write(t("history_delete_subtitle"))
    
    if filtered_logs.empty:
        st.caption(t("history_no_filtered_entries"))
        return

    # Optionen für das Dropdown-Menü lesbar und lokalisiert formatieren
    delete_options = []
    for _, row in filtered_logs.iterrows():
        # Holt die übersetzte Zählerbezeichnung
        meter_label_trans = t(option_key_map.get(row["meter"], row["meter"]))
        delete_options.append({
            "id": row["id"],
            "label": f"ID {row['id']} | {row['date']} | {meter_label_trans} | {t('history_reading_label')}: {row['reading']:,.3f}"
        })
        
    target_record = st.selectbox(
        t("history_delete_select_label"),
        options=delete_options,
        format_func=lambda x: x["label"] if x else ""
    )
    
    # Sicherheitsabfrage für statische Code-Analyse (Pylance) und Laufzeit-Schutz
    if target_record is not None:
        # Zweistufige Bestätigung via Popover zum Schutz vor Fehlklicks
        with st.popover(t("history_popover_confirm"), width="stretch"):
            st.warning(t("history_delete_warning").format(label=target_record['label']))
            
            confirm_delete = st.button(
                t("history_delete_btn"), 
                type="primary", 
                width="stretch"
            )
            
            if confirm_delete:
                # UX-Spinner & Toast während des Löschvorgangs
                with st.spinner(t("history_deleting_spinner").format(id=target_record['id'])):
                    db.execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(target_record["id"])})
                
                # CACHE-BUSTING: Logs und Berechnungen verwerfen
                st.session_state.pop("logs", None)
                st.session_state.pop("processed_logs", None)
                st.session_state.pop("stats", None)
                
                st.toast(t("history_success_toast").format(id=target_record['id']), icon="🗑️")
                st.rerun()