# ui_manage_history.py
import streamlit as st
import database as db

def render_page(current_user_id, logs):
    st.title("Manage Data History")
    
    if logs.empty:
        st.info("No recorded database entries found.")
    else:
        st.subheader("Saved Log Entries")
        st.dataframe(logs.drop(columns=["user_id"], errors="ignore"), use_container_width=True)
        
        st.markdown("---")
        st.subheader("Delete Log Entry")
        
        delete_id = st.number_input(
            "Enter Entry 'id' to remove", 
            min_value=int(logs['id'].min()), 
            max_value=int(logs['id'].max()), 
            step=1
        )
        
        confirm_delete = st.button("Delete Entry", type="primary")
            
        if confirm_delete:
            target_row = db.run_query("SELECT user_id FROM logs WHERE id = :id", {"id": int(delete_id)})
            if not target_row.empty and str(target_row.iloc[0]['user_id']) == str(current_user_id):
                db.execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(delete_id)})
                st.success(f"Record with ID {delete_id} deleted successfully.")
                st.rerun()
            else:
                st.error("Invalid entry ID or permission denied.")