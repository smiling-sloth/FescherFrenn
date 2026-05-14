import tkinter as tk
from tkinter import ttk, Toplevel, messagebox, filedialog
from tkcalendar import DateEntry
import json
import os
from datetime import datetime
import getpass
import logging
import re
import webbrowser

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
except ImportError:
    pass

TEMP_DATA_FILE = "temp_fishing_data.json"
BACKUP_DIR = os.path.expanduser("~/FescherfrennData/backups")
APP_VERSION = "1.1"

# Set up logging
logging.basicConfig(filename='fescherfrenn.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

LANGUAGES = {
    "English": {
        "title": "Fëscherfrënn Stengefort Fishing Competition Register",
        "select_lang": "Select Language",
        "event_name": "Event Name:",
        "location": "Location:",
        "date": "Date:",
        "add_participant": "Add new participant",
        "name": "Name:",
        "club": "Club:",
        "category": "Category:",
        "remark": "Remark:",
        "fish_type": "Fish Type:",
        "log_catch": "Log Catch",
        "fish_weight": "Weight (kg):",
        "fish_length": "Length (cm):",
        "num_catches": "Number of Catches:",
        "live_rankings": "Live Rankings",
        "total_weight": "Top 3 Total Weight",
        "longest_fish": "Top 3 Longest Fish",
        "heaviest_fish": "Top 3 Heaviest Fish",
        "num_catches_label": "Top 3 Most Catches",
        "generate_report": "Generate Report",
        "reset_event": "Reset Event",
        "export_event": "Export Event",
        "import_event": "Import Event",
        "help": "Help",
        "confirm_reset": "Are you sure you want to reset all data?",
        "confirm_close": "Are you sure you want to close the app? Unsaved data will be saved.",
        "saved": "Data saved!",
        "report_generated": "Report saved as '[date]_[event_name].pdf'!",
        "import_success": "Success! Event imported!",
        "export_success": "Success! Event exported to {filename}!",
        "reset_success": "Success! Event reset!",
        "number_of_catches": "Number of Catches",
        "error": "Error: Please fill all fields correctly.",
        "event_error": "Error: Please enter both event name and location.",
        "duplicate_name": "Error: Participant name already exists!",
        "participants": "Participants",
        "copyright": "© 2025 Fëscherfrënn Stengefort Fishing Competition Register - Robert Androvics, fescherfrenn@outlook.com",
        "tooltip_add": "Add a new participant",
        "tooltip_log": "Log a fish catch",
        "tooltip_report": "Generate PDF report",
        "tooltip_reset": "Reset all data",
        "tooltip_export": "Export event to JSON",
        "tooltip_import": "Import event from JSON",
        "tooltip_help": "View user manual",
        "summary_report": "Event Summary Report",
        "summary": "Summary:",
        "table_participants": "Number of Catches",
        "table_total_weight": "Total Weight (kg)",
        "table_longest_fish": "Longest Fish (cm)",
        "table_club": "Club",
        "table_category": "Category",
        "table_remark": "Remark",
        "summary_participants": "participants",
        "summary_total_catches": "total catches",
        "summary_total_weight": "kg total weight",
        "indiv_time": "Time",
        "indiv_type": "Fish Type",
        "indiv_weight": "Weight (kg)",
        "indiv_length": "Length (cm)",
        "indiv_total_catches": "Total Catches",
        "indiv_total_weight": "Total Weight",
        "indiv_final_rank": "Final Rank by Total Weight",
        "event_details": "Event Details",
        "permission_error": "Permission denied: Could not save data to '[folder]'. Please run with administrator privileges or choose a different directory.",
        "invalid_number": "Error: Enter a valid positive number.",
        "invalid_catches": "Error: Number of catches must be a positive integer.",
        "yes": "Yes",
        "no": "No",
        "close": "Close",
        "contact": "Contact",
        "contact_text": "For support, contact Robert Androvics at fescherfrenn@outlook.com.",
        "select_participant": "Select a participant",
        "category_options": {
            "": "",
            "Senior": "Senior",
            "Master": "Master",
            "Veteran": "Veteran",
            "Lady": "Lady",
            "U20": "U20",
            "U15": "U15",
            "U10": "U10"
        },
        "help_manual": (
            "Fëscherfrënn Stengefort Fishing Competition Register v1.1\n\n"
            "Contact\n"
            "For support, contact Robert Androvics at fescherfrenn@outlook.com.\n\n"
            "Starting the Application\n"
            "Launch the Fescherfrenn application by double-clicking the executable (e.g., 'fescherfrenn.exe' on Windows or 'Fescherfrenn.app' on macOS). Ensure 'logo.png' is in the same directory for the UI logo and 'logo.ico' (optional) for the app icon on Windows. Select your language (English, French, German, Luxembourgish) and click to proceed.\n\n"
            "Creating an Event\n"
            "Enter the event name, location, and date in the 'Event Details' section. Event name and location are mandatory before adding participants or logging catches. Once saved, these fields are locked. Example: Name: 'Spring Fishing', Location: 'Lake', Date: '08/04/2025'.\n\n"
            "Adding Participants\n"
            "Click 'Add new participant' to open a dialog. Enter the participant's name (mandatory), club (optional, max 64 characters), category (optional, select from Senior, Master, Veteran, Lady, U20, U15, U10), and remark (optional, max 64 characters). Names must be unique. Once added, these details cannot be modified. The participant list updates on the right and is read-only, showing only names.\n\n"
            "Logging Catches\n"
            "Select a participant from the dropdown (or type to search), enter the weight (kg, mandatory), number of catches (default 1, min 1), length (cm, optional), and fish type (optional). Click 'Log Catch'. For multiple catches (>1), length and type are set to empty and only count toward total weight and catch count. Weight and length must be positive numbers (e.g., 1.5 or 1,5 in French/German/Luxembourgish). Live rankings update automatically.\n\n"
            "Generating Reports\n"
            "Click 'Generate Report' to create a PDF with event summaries (including club, category, remark) and participant details (club, category, remark below catch table). Saved as '[date]_[event_name].pdf' (e.g., '20250408_Spring_Fishing.pdf'). All table cells are word-wrapped.\n\n"
            "Exporting and Importing Events\n"
            "Use 'Export Event' to save event data as a JSON file. Use 'Import Event' to load a previous event. Version 1.0 imports set number of catches to 1 and may lack club/category/remark. Ensure the file version matches the app version (1.1).\n\n"
            "Resetting the Event\n"
            "Click 'Reset Event' to clear all data. Confirm with 'Yes' (default, press Enter) or 'No'. Backups are saved in '~/FescherfrennData/backups'.\n\n"
            "Troubleshooting\n"
            "If the app fails to save, check folder permissions or run as administrator (Windows) or ensure write access (macOS). Errors are logged to 'fescherfrenn.log'. View the manual via the 'Help' button. If 'logo.ico' is missing, the app uses the default icon."
        )
    },
    "French": {
        "title": "Registre de Compétition de Pêche Fëscherfrënn Stengefort",
        "select_lang": "Sélectionnez la langue",
        "event_name": "Nom de l'événement :",
        "location": "Lieu :",
        "date": "Date :",
        "add_participant": "Ajouter un nouveau participant",
        "name": "Nom :",
        "club": "Société :",
        "category": "Catégorie :",
        "remark": "Remarque :",
        "fish_type": "Type de poisson :",
        "log_catch": "Enregistrer la prise",
        "fish_weight": "Poids (kg) :",
        "fish_length": "Longueur (cm) :",
        "num_catches": "Nombre de prises :",
        "live_rankings": "Classements en direct",
        "total_weight": "Top 3 Poids total",
        "longest_fish": "Top 3 Plus long poisson",
        "heaviest_fish": "Top 3 Plus lourd poisson",
        "num_catches_label": "Top 3 Plus de prises",
        "generate_report": "Générer le rapport",
        "reset_event": "Réinitialiser l'événement",
        "export_event": "Exporter l'événement",
        "import_event": "Importer l'événement",
        "help": "Aide",
        "confirm_reset": "Êtes-vous sûr de vouloir réinitialiser toutes les données ?",
        "confirm_close": "Êtes-vous sûr de vouloir fermer l'application ? Les données non enregistrées seront sauvegardées.",
        "saved": "Données enregistrées !",
        "report_generated": "Rapport enregistré sous '[date]_[event_name].pdf' !",
        "import_success": "Succès ! Événement importé !",
        "export_success": "Succès ! Événement exporté vers {filename} !",
        "reset_success": "Succès ! Événement réinitialisé !",
        "number_of_catches": "Nombre de prises",
        "error": "Erreur : Veuillez remplir tous les champs correctement.",
        "event_error": "Erreur : Veuillez entrer à la fois le nom de l'événement et le lieu.",
        "duplicate_name": "Erreur : Le nom du participant existe déjà !",
        "participants": "Participants",
        "copyright": "© 2025 Registre de Compétition de Pêche Fëscherfrënn Stengefort - Robert Androvics, fescherfrenn@outlook.com",
        "tooltip_add": "Ajouter un nouveau participant",
        "tooltip_log": "Enregistrer une prise de poisson",
        "tooltip_report": "Générer un rapport PDF",
        "tooltip_reset": "Réinitialiser toutes les données",
        "tooltip_export": "Exporter l'événement au format JSON",
        "tooltip_import": "Importer l'événement depuis JSON",
        "tooltip_help": "Voir le manuel d'utilisation",
        "summary_report": "Rapport récapitulatif de l'événement",
        "summary": "Résumé :",
        "table_participants": "Nombre de prises",
        "table_total_weight": "Poids total (kg)",
        "table_longest_fish": "Plus long poisson (cm)",
        "table_club": "Société",
        "table_category": "Catégorie",
        "table_remark": "Remarque",
        "summary_participants": "participants",
        "summary_total_catches": "prises totales",
        "summary_total_weight": "kg de poids total",
        "indiv_time": "Heure",
        "indiv_type": "Type de poisson",
        "indiv_weight": "Poids (kg)",
        "indiv_length": "Longueur (cm)",
        "indiv_total_catches": "Prises totales",
        "indiv_total_weight": "Poids total",
        "indiv_final_rank": "Classement final par poids total",
        "event_details": "Détails de l'événement",
        "permission_error": "Permission refusée : Impossible d'enregistrer les données dans '[folder]'. Veuillez exécuter avec les privilèges administrateur ou choisir un autre répertoire.",
        "invalid_number": "Erreur : Entrez un nombre positif valide.",
        "invalid_catches": "Erreur : Le nombre de prises doit être un entier positif.",
        "yes": "Oui",
        "no": "Non",
        "close": "Fermer",
        "contact": "Contact",
        "contact_text": "Pour assistance, contactez Robert Androvics à fescherfrenn@outlook.com.",
        "select_participant": "Sélectionnez un participant",
        "category_options": {
            "": "",
            "Senior": "Senior",
            "Master": "Maître",
            "Veteran": "Vétéran",
            "Lady": "Dame",
            "U20": "U20",
            "U15": "U15",
            "U10": "U10"
        },
        "help_manual": (
            "Registre de Compétition de Pêche Fëscherfrënn Stengefort v1.1\n\n"
            "Contact\n"
            "Pour toute assistance, contactez Robert Androvics à fescherfrenn@outlook.com.\n\n"
            "Démarrer l'Application\n"
            "Lancez l'application Fescherfrenn en double-cliquant sur l'exécutable (par exemple, 'fescherfrenn.exe' sur Windows ou 'Fescherfrenn.app' sur macOS). Assurez-vous que 'logo.png' est dans le même répertoire pour le logo de l'interface utilisateur et 'logo.ico' (optionnel) pour l'icône de l'application sur Windows. Sélectionnez votre langue (anglais, français, allemand, luxembourgeois) et cliquez pour continuer.\n\n"
            "Créer un Événement\n"
            "Entrez le nom de l'événement, le lieu et la date dans la section 'Détails de l'événement'. Le nom de l'événement et le lieu sont obligatoires avant d'ajouter des participants ou d'enregistrer des prises. Une fois enregistrés, ces champs sont verrouillés. Exemple : Nom : 'Pêche de printemps', Lieu : 'Lac', Date : '08/04/2025'.\n\n"
            "Ajouter des Participants\n"
            "Cliquez sur 'Ajouter un nouveau participant' pour ouvrir une boîte de dialogue. Entrez le nom du participant (obligatoire), la société (optionnelle, max 64 caractères), la catégorie (optionnelle, sélectionnez parmi Senior, Maître, Vétéran, Dame, U20, U15, U10), et la remarque (optionnelle, max 64 caractères). Les noms doivent être uniques. Une fois ajoutés, ces détails ne peuvent pas être modifiés. La liste des participants est mise à jour à droite et est en lecture seule, affichant uniquement les noms.\n\n"
            "Enregistrer des Prises\n"
            "Sélectionnez un participant dans la liste déroulante (ou tapez pour rechercher), entrez le poids (kg, obligatoire), le nombre de prises (par défaut 1, min 1), la longueur (cm, optionnelle), et le type de poisson (optionnel). Cliquez sur 'Enregistrer la prise'. Pour plusieurs prises (>1), la longueur et le type sont définis comme vides et ne comptent que pour le poids total et le nombre de prises. Le poids et la longueur doivent être des nombres positifs (par exemple, 1,5 ou 1.5 en français/allemand/luxembourgeois). Les classements en direct sont mis à jour automatiquement.\n\n"
            "Générer des Rapports\n"
            "Cliquez sur 'Générer le rapport' pour créer un PDF avec les résumés de l'événement (y compris la société, la catégorie, la remarque) et les détails des participants (société, catégorie, remarque sous le tableau des prises). Enregistré sous '[date]_[event_name].pdf' (par exemple, '20250408_Pêche_de_printemps.pdf'). Toutes les cellules du tableau sont enveloppées.\n\n"
            "Exporter et Importer des Événements\n"
            "Utilisez 'Exporter l'événement' pour sauvegarder les données de l'événement sous forme de fichier JSON. Utilisez 'Importer l'événement' pour charger un événement précédent. Les importations de la version 1.0 définissent le nombre de prises à 1 et peuvent manquer de société/catégorie/remarque. Assurez-vous que la version du fichier correspond à la version de l'application (1.1).\n\n"
            "Réinitialiser l'Événement\n"
            "Cliquez sur 'Réinitialiser l'événement' pour effacer toutes les données. Confirmez avec 'Oui' (par défaut, appuyez sur Entrée) ou 'Non'. Les sauvegardes sont enregistrées dans '~/FescherfrennData/backups'.\n\n"
            "Dépannage\n"
            "Si l'application ne parvient pas à enregistrer, vérifiez les permissions du dossier ou exécutez en tant qu'administrateur (Windows) ou assurez-vous d'avoir les droits d'écriture (macOS). Les erreurs sont consignées dans 'fescherfrenn.log'. Consultez le manuel via le bouton 'Aide'. Si 'logo.ico' est manquant, l'application utilise l'icône par défaut."
        )
    },
    "German": {
        "title": "Fëscherfrënn Stengefort Angelwettbewerb Register",
        "select_lang": "Sprache auswählen",
        "event_name": "Veranstaltungsname:",
        "location": "Ort:",
        "date": "Datum:",
        "add_participant": "Neuen Teilnehmer hinzufügen",
        "name": "Name:",
        "club": "Verein:",
        "category": "Kategorie:",
        "remark": "Bemerkung:",
        "fish_type": "Fischart:",
        "log_catch": "Fang protokollieren",
        "fish_weight": "Gewicht (kg):",
        "fish_length": "Länge (cm):",
        "num_catches": "Anzahl der Fänge:",
        "live_rankings": "Live-Ranglisten",
        "total_weight": "Top 3 Gesamtgewicht",
        "longest_fish": "Top 3 Längster Fisch",
        "heaviest_fish": "Top 3 Schwerster Fisch",
        "num_catches_label": "Top 3 Meiste Fänge",
        "generate_report": "Bericht generieren",
        "reset_event": "Veranstaltung zurücksetzen",
        "export_event": "Veranstaltung exportieren",
        "import_event": "Veranstaltung importieren",
        "help": "Hilfe",
        "confirm_reset": "Sind Sie sicher, dass Sie alle Daten zurücksetzen möchten?",
        "confirm_close": "Sind Sie sicher, dass Sie die App schließen möchten? Nicht gespeicherte Daten werden gespeichert.",
        "saved": "Daten gespeichert!",
        "report_generated": "Bericht als '[date]_[event_name].pdf' gespeichert!",
        "import_success": "Erfolg! Veranstaltung importiert!",
        "export_success": "Erfolg! Veranstaltung exportiert nach {filename}!",
        "reset_success": "Erfolg! Veranstaltung zurückgesetzt!",
        "number_of_catches": "Anzahl der Fänge",
        "error": "Fehler: Bitte füllen Sie alle Felder korrekt aus.",
        "event_error": "Fehler: Bitte geben Sie sowohl den Veranstaltungsnamen als auch den Ort ein.",
        "duplicate_name": "Fehler: Teilnehmername existiert bereits!",
        "participants": "Teilnehmer",
        "copyright": "© 2025 Fëscherfrënn Stengefort Angelwettbewerb Register - Robert Androvics, fescherfrenn@outlook.com",
        "tooltip_add": "Neuen Teilnehmer hinzufügen",
        "tooltip_log": "Fischfang protokollieren",
        "tooltip_report": "PDF-Bericht generieren",
        "tooltip_reset": "Alle Daten zurücksetzen",
        "tooltip_export": "Veranstaltung als JSON exportieren",
        "tooltip_import": "Veranstaltung aus JSON importieren",
        "tooltip_help": "Benutzerhandbuch anzeigen",
        "summary_report": "Veranstaltungsübersichtsbericht",
        "summary": "Zusammenfassung:",
        "table_participants": "Anzahl der Fänge",
        "table_total_weight": "Gesamtgewicht (kg)",
        "table_longest_fish": "Längster Fisch (cm)",
        "table_club": "Verein",
        "table_category": "Kategorie",
        "table_remark": "Bemerkung",
        "summary_participants": "Teilnehmer",
        "summary_total_catches": "Gesamtfänge",
        "summary_total_weight": "kg Gesamtgewicht",
        "indiv_time": "Zeit",
        "indiv_type": "Fischart",
        "indiv_weight": "Gewicht (kg)",
        "indiv_length": "Länge (cm)",
        "indiv_total_catches": "Gesamtfänge",
        "indiv_total_weight": "Gesamtgewicht",
        "indiv_final_rank": "Endrang nach Gesamtgewicht",
        "event_details": "Veranstaltungsdetails",
        "permission_error": "Zugriff verweigert: Konnte Daten nicht in '[folder]' speichern. Bitte mit Administratorrechten ausführen oder ein anderes Verzeichnis wählen.",
        "invalid_number": "Fehler: Geben Sie eine gültige positive Zahl ein.",
        "invalid_catches": "Fehler: Die Anzahl der Fänge muss eine positive Ganzzahl sein.",
        "yes": "Ja",
        "no": "Nein",
        "close": "Schließen",
        "contact": "Kontakt",
        "contact_text": "Für Unterstützung wenden Sie sich an Robert Androvics unter fescherfrenn@outlook.com.",
        "select_participant": "Wählen Sie einen Teilnehmer",
        "category_options": {
            "": "",
            "Senior": "Senior",
            "Master": "Meister",
            "Veteran": "Veteran",
            "Lady": "Dame",
            "U20": "U20",
            "U15": "U15",
            "U10": "U10"
        },
        "help_manual": (
            "Fëscherfrënn Stengefort Angelwettbewerb Register v1.1\n\n"
            "Kontakt\n"
            "Für Unterstützung wenden Sie sich an Robert Androvics unter fescherfrenn@outlook.com.\n\n"
            "Starten der Anwendung\n"
            "Starten Sie die Fescherfrenn-Anwendung durch Doppelklick auf die ausführbare Datei (z.B. 'fescherfrenn.exe' unter Windows oder 'Fescherfrenn.app' unter macOS). Stellen Sie sicher, dass 'logo.png' im selben Verzeichnis für das UI-Logo und 'logo.ico' (optional) für das App-Symbol unter Windows vorhanden ist. Wählen Sie Ihre Sprache (Englisch, Französisch, Deutsch, Luxemburgisch) und klicken Sie, um fortzufahren.\n\n"
            "Erstellen eines Events\n"
            "Geben Sie den Veranstaltungsnamen, den Ort und das Datum im Abschnitt 'Veranstaltungsdetails' ein. Veranstaltungsname und Ort sind obligatorisch, bevor Teilnehmer hinzugefügt oder Fänge protokolliert werden können. Nach dem Speichern sind diese Felder gesperrt. Beispiel: Name: 'Frühjahrsangeln', Ort: 'See', Datum: '08.04.2025'.\n\n"
            "Hinzufügen von Teilnehmern\n"
            "Klicken Sie auf 'Neuen Teilnehmer hinzufügen', um einen Dialog zu öffnen. Geben Sie den Namen des Teilnehmers (obligatorisch), den Verein (optional, max. 64 Zeichen), die Kategorie (optional, wählen Sie aus Senior, Meister, Veteran, Dame, U20, U15, U10) und die Bemerkung (optional, max. 64 Zeichen) ein. Namen müssen einzigartig sein. Einmal hinzugefügt, können diese Details nicht mehr geändert werden. Die Teilnehmerliste wird rechts aktualisiert und ist schreibgeschützt, zeigt nur Namen an.\n\n"
            "Protokollieren von Fängen\n"
            "Wählen Sie einen Teilnehmer aus der Dropdown-Liste (oder tippen Sie zum Suchen), geben Sie das Gewicht (kg, obligatorisch), die Anzahl der Fänge (Standard 1, min 1), die Länge (cm, optional) und die Fischart (optional) ein. Klicken Sie auf 'Fang protokollieren'. Bei mehreren Fängen (>1) werden Länge und Art leer gesetzt und zählen nur zum Gesamtgewicht und zur Fangzahl. Gewicht und Länge müssen positive Zahlen sein (z.B. 1,5 oder 1.5 in Französisch/Deutsch/Luxemburgisch). Live-Ranglisten werden automatisch aktualisiert.\n\n"
            "Generieren von Berichten\n"
            "Klicken Sie auf 'Bericht generieren', um ein PDF mit Veranstaltungszusammenfassungen (einschließlich Verein, Kategorie, Bemerkung) und Teilnehmerdetails (Verein, Kategorie, Bemerkung unter der Fangtabelle) zu erstellen. Gespeichert als '[date]_[event_name].pdf' (z.B. '20250408_Frühjahrsangeln.pdf'). Alle Tabellenzellen sind umbrochen.\n\n"
            "Exportieren und Importieren von Events\n"
            "Verwenden Sie 'Veranstaltung exportieren', um Eventdaten als JSON-Datei zu speichern. Verwenden Sie 'Veranstaltung importieren', um ein vorheriges Event zu laden. Importe der Version 1.0 setzen die Anzahl der Fänge auf 1 und können Verein/Kategorie/Bemerkung fehlen. Stellen Sie sicher, dass die Dateiversion mit der App-Version (1.1) übereinstimmt.\n\n"
            "Zurücksetzen des Events\n"
            "Klicken Sie auf 'Veranstaltung zurücksetzen', um alle Daten zu löschen. Bestätigen Sie mit 'Ja' (Standard, drücken Sie Enter) oder 'Nein'. Backups werden in '~/FescherfrennData/backups' gespeichert.\n\n"
            "Fehlerbehebung\n"
            "Wenn die App nicht speichert, überprüfen Sie die Ordnerberechtigungen oder führen Sie sie als Administrator aus (Windows) oder stellen Sie sicher, dass Schreibzugriff besteht (macOS). Fehler werden in 'fescherfrenn.log' protokolliert. Sehen Sie das Handbuch über den 'Hilfe'-Button. Wenn 'logo.ico' fehlt, verwendet die App das Standard-Symbol."
        )
    },
    "Luxembourgish": {
        "title": "Fëscherfrënn Stengefort Fëschkonkurrenz Register",
        "select_lang": "Sprooch wielen",
        "event_name": "Evenement Numm:",
        "location": "Plaz:",
        "date": "Datum:",
        "add_participant": "Neie Participant derbäisetzen",
        "name": "Numm:",
        "club": "Verein:",
        "category": "Kategorie:",
        "remark": "Bemierkung:",
        "fish_type": "Fësch Typ:",
        "log_catch": "Fësch fangen",
        "fish_weight": "Gewiicht (kg):",
        "fish_length": "Längt (cm):",
        "num_catches": "Zuel vun de Fäng:",
        "live_rankings": "Live Klassementer",
        "total_weight": "Top 3 Gesamtgewiicht",
        "longest_fish": "Top 3 Längste Fësch",
        "heaviest_fish": "Top 3 Schwéierste Fësch",
        "num_catches_label": "Top 3 Meescht Fäng",
        "generate_report": "Bericht generéieren",
        "reset_event": "Evenement zrécksetzen",
        "export_event": "Evenement exportéieren",
        "import_event": "Evenement importéieren",
        "help": "Hëllef",
        "confirm_reset": "Sidd Dir sécher, datt Dir all Donnéeë zrécksetze wëllt?",
        "confirm_close": "Sidd Dir sécher, datt Dir d'App zoumaache wëllt? Net gespäichert Donnéeë ginn gespäichert.",
        "saved": "Daten gespäichert!",
        "report_generated": "Bericht als '[date]_[event_name].pdf' gespäichert!",
        "import_success": "Erfolleg! Evenement importéiert!",
        "export_success": "Erfolleg! Evenement exportéiert op {filename}!",
        "reset_success": "Erfolleg! Evenement zréckgesat!",
        "number_of_catches": "Zuel vun de Fäng",
        "error": "Feeler: Fëllt w.e.g. all Felder korrekt aus.",
        "event_error": "Feeler: Gitt w.e.g. souwuel den Evenementnumm wéi och d'Plaz an.",
        "duplicate_name": "Feeler: Participantnumm existéiert schonn!",
        "participants": "Participanten",
        "copyright": "© 2025 Fëscherfrënn Stengefort Fëschkonkurrenz Register - Robert Androvics, fescherfrenn@outlook.com",
        "tooltip_add": "Neie Participant derbäisetzen",
        "tooltip_log": "Fëschfang protokollieren",
        "tooltip_report": "PDF-Bericht generéieren",
        "tooltip_reset": "All Daten zrécksetzen",
        "tooltip_export": "Evenement als JSON exportéieren",
        "tooltip_import": "Evenement aus JSON importéieren",
        "tooltip_help": "Benotzerhandbuch weisen",
        "summary_report": "Evenement Iwwerbléck Bericht",
        "summary": "Resumé:",
        "table_participants": "Zuel vun de Fäng",
        "table_total_weight": "Gesamtgewiicht (kg)",
        "table_longest_fish": "Längste Fësch (cm)",
        "table_club": "Verein",
        "table_category": "Kategorie",
        "table_remark": "Bemierkung",
        "summary_participants": "Participanten",
        "summary_total_catches": "Gesamtfäng",
        "summary_total_weight": "kg Gesamtgewiicht",
        "indiv_time": "Zäit",
        "indiv_type": "Fësch Typ",
        "indiv_weight": "Gewiicht (kg)",
        "indiv_length": "Längt (cm)",
        "indiv_total_catches": "Gesamtfäng",
        "indiv_total_weight": "Gesamtgewiicht",
        "indiv_final_rank": "Finale Rang no Gesamtgewiicht",
        "event_details": "Evenement Detailer",
        "permission_error": "Zougang verweigert: Konnt Donnéeë net an '[folder]' späicheren. Führt w.e.g. mat Administrateur Rechter aus oder wielt en aneren Dossier.",
        "invalid_number": "Feeler: Gitt eng gëlteg positiv Zuel an.",
        "invalid_catches": "Feeler: D'Zuel vun de Fäng muss eng positiv Ganzzuel sinn.",
        "yes": "Jo",
        "no": "Nee",
        "close": "Zoumaachen",
        "contact": "Kontakt",
        "contact_text": "Fir Ënnerstëtzung, kontaktéiert de Robert Androvics op fescherfrenn@outlook.com.",
        "select_participant": "Wielt e Participant",
        "category_options": {
            "": "",
            "Senior": "Senior",
            "Master": "Meeschter",
            "Veteran": "Veteran",
            "Lady": "Damm",
            "U20": "U20",
            "U15": "U15",
            "U10": "U10"
        },
        "help_manual": (
            "Fëscherfrënn Stengefort Fëschkonkurrenz Register v1.1\n\n"
            "Kontakt\n"
            "Fir Ënnerstëtzung, kontaktéiert de Robert Androvics op fescherfrenn@outlook.com.\n\n"
            "D'Applikatioun Starten\n"
            "Start d'Fescherfrenn Applikatioun andeems Dir duebel klickt op d'Ausféierbar Datei (z.B. 'fescherfrenn.exe' op Windows oder 'Fescherfrenn.app' op macOS). Vergewëssert Iech datt 'logo.png' am selwechte Verzeichnis fir d'UI-Logo an 'logo.ico' (optional) fir d'App-Ikon op Windows ass. Wielt Är Sprooch (Englesch, Franséisch, Däitsch, Lëtzebuergesch) a klickt fir weiderzemaachen.\n\n"
            "E Evenement erstellen\n"
            "Gitt den Evenementnumm, d'Plaz an den Datum am Abschnitt 'Evenement Detailer' an. Evenementnumm an Plaz sinn obligatoresch ier Dir Participanten derbäisetzt oder Fäng protokolliert. Eemol gespäichert, sinn dës Felder gespaart. Beispill: Numm: 'Fréijoersfësch', Plaz: 'Séi', Datum: '08/04/2025'.\n\n"
            "Participanten derbäisetzen\n"
            "Klickt op 'Neie Participant derbäisetzen' fir en Dialog opzehuelen. Gitt den Numm vum Participant (obligatoresch), de Verein (optional, max 64 Zeechen), d'Kategorie (optional, wielt aus Senior, Meeschter, Veteran, Damm, U20, U15, U10), an d'Bemierkung (optional, max 64 Zeechen). Nimm mussen eenzegaarteg sinn. Eemol derbäigesat, kënnen dës Detailer net méi geännert ginn. D'Participantelëscht gëtt riets aktualiséiert an ass nëmmen liesbar, weist nëmmen Nimm.\n\n"
            "Fäng protokollieren\n"
            "Wielt e Participant aus der Dropdown-Lëscht (oder tippt fir ze sichen), ginn d'Gewiicht (kg, obligatoresch), d'Zuel vun de Fäng (Standard 1, min 1), d'Längt (cm, optional), an de Fësch Typ (optional) an. Klickt op 'Fësch fangen'. Fir méi Fäng (>1), Längt an Typ sinn eidel gesat a zielen nëmmen fir Gesamtgewiicht an Fangzuel. Gewiicht an Längt mussen positiv Zuelen sinn (z.B. 1,5 oder 1.5 op Franséisch/Däitsch/Lëtzebuergesch). Live Klassementer ginn automatesch aktualiséiert.\n\n"
            "Berichter generéieren\n"
            "Klickt op 'Bericht generéieren' fir e PDF mat Evenement Resuméen (dorënner Verein, Kategorie, Bemierkung) an Participant Detailer (Verein, Kategorie, Bemierkung ënner der Fangtabell) ze erstellen. Gespeichert als '[date]_[event_name].pdf' (z.B. '20250408_Fréijoersfësch.pdf'). All Tabellzellen sinn ëmgeklappt.\n\n"
            "Evenementer exportéieren an importéieren\n"
            "Benotzt 'Evenement exportéieren' fir Eventdaten als JSON-Datei ze späicheren. Benotzt 'Evenement importéieren' fir e virdrun Evenement ze lueden. Importe vun der Versioun 1.0 setzen d'Zuel vun de Fäng op 1 an kënnen Verein/Kategorie/Bemierkung feelen. Vergewëssert Iech datt d'Dateiversioun mat der App-Versioun (1.1) übereenstëmmt.\n\n"
            "Evenement zrécksetzen\n"
            "Klickt op 'Evenement zrécksetzen' fir all Donnéeën ze läschen. Bestätegt mat 'Jo' (Standard, dréckt Enter) oder 'Nee'. Backups ginn an '~/FescherfrennData/backups' gespäichert.\n\n"
            "Feelerbehandlung\n"
            "Wann d'App net späichert, iwwerpréift d'Dossierberechtigungen oder führt se als Administrator aus (Windows) oder stellt sécher, datt Schreifzougang besteet (macOS). Feeler ginn an 'fescherfrenn.log' protokolliéiert. Kuckt d'Handbuch iwwer de 'Hëllef'-Knopf. Wann 'logo.ico' feelt, benotzt d'App d'Standard-Ikon."
        )
    }
}

def get_event_folder(event):
    """Helper function to construct event folder path and filename."""
    if not event or not all(event.values()):
        return f"{datetime.now().strftime('%Y%m%d')}_event"
    event_name = str(event.get("name", "event")).replace(" ", "_")
    event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
    try:
        date_obj = datetime.strptime(event_date, "%d/%m/%Y")
        date_str = date_obj.strftime("%Y%m%d")
    except ValueError:
        date_str = datetime.now().strftime("%Y%m%d")
    return f"{date_str}_{event_name}"

def load_data(event=None):
    """Load data from event-specific folder if available, else working directory."""
    try:
        if event and all(event.values()):
            folder_name = get_event_folder(event)
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            if os.path.exists(data_file):
                with open(data_file, 'r') as file:
                    data = json.load(file)
                # Ensure new fields for backward compatibility
                for name in data["participants"]:
                    if not isinstance(data["participants"][name], dict):
                        data["participants"][name] = {
                            "id": data["participants"][name],
                            "club": "",
                            "category": "",
                            "remark": ""
                        }
                return data
        if os.path.exists(TEMP_DATA_FILE):
            with open(TEMP_DATA_FILE, 'r') as file:
                data = json.load(file)
                for name in data["participants"]:
                    if not isinstance(data["participants"][name], dict):
                        data["participants"][name] = {
                            "id": data["participants"][name],
                            "club": "",
                            "category": "",
                            "remark": ""
                        }
                return data
    except Exception as e:
        logging.error(f"load_data failed: {str(e)}")
    return {"event": {}, "participants": {}, "catches": {}, "lang": "English", "version": APP_VERSION}

def save_data(data, event=None):
    """Save data to event-specific folder with dynamic filename, fallback to user directory."""
    try:
        data["version"] = APP_VERSION
        if event and all(event.values()):
            folder_name = get_event_folder(event)
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            try:
                os.makedirs(folder_name, exist_ok=True)
                with open(data_file, 'w') as file:
                    json.dump(data, file, indent=4)
                try:
                    os.makedirs(BACKUP_DIR, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_file = os.path.join(BACKUP_DIR, f"backup_{folder_name}_{timestamp}.json")
                    with open(backup_file, 'w') as file:
                        json.dump(data, file, indent=4)
                except Exception as e:
                    logging.error(f"Backup failed: {str(e)}")
                return
            except PermissionError:
                messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["permission_error"].replace("[folder]", folder_name))
        fallback_dir = os.path.expanduser("~/FescherfrennData")
        data_file = os.path.join(fallback_dir, TEMP_DATA_FILE)
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            with open(data_file, 'w') as file:
                json.dump(data, file, indent=4)
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(BACKUP_DIR, f"backup_temp_{timestamp}.json")
                with open(backup_file, 'w') as file:
                    json.dump(data, file, indent=4)
            except Exception as e:
                logging.error(f"Backup failed: {str(e)}")
        except Exception:
            messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["error"])
    except Exception as e:
        logging.error(f"save_data failed: {str(e)}")
        messagebox.showerror("Error", LANGUAGES[data.get("lang", "English")]["error"])

class FishingApp:
    def __init__(self, root):
        self.root = root
        try:
            self.data = load_data()
            self.lang = self.data.get("lang", "English")
            self.data["lang"] = self.lang
            self.root.title(LANGUAGES[self.lang]["title"])
            try:
                self.root.iconbitmap("logo.ico")
            except tk.TclError:
                logging.warning("logo.ico not found, using default icon")
            
            self.root.state('zoomed')
            self.root.minsize(1360, 768)
            screen_width = self.root.winfo_screenwidth()
            self.font_size = 12 if screen_width <= 1366 else 16

            self.rankings = None
            self.participants_list = None
            self.report_btn = None
            self.reset_btn = None
            self.export_btn = None
            self.import_btn = None
            self.help_btn = None
            self.catch_name_var = None  # Added for Combobox hint

            self.canvas = tk.Canvas(self.root)
            self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
            self.main_frame = ttk.Frame(self.canvas)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            self.canvas_frame = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
            self.main_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.root.bind("<Configure>", self.on_resize)

            try:
                self.logo = tk.PhotoImage(file="logo.png")
                self.logo_label = ttk.Label(self.main_frame, image=self.logo)
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")
            except Exception:
                self.logo_label = ttk.Label(self.main_frame, text="Logo Placeholder (200x200px)", width=28, anchor="center")
                self.logo_label.grid(row=0, column=0, pady=5, padx=5, sticky="nw")

            self.lang_frame = ttk.Frame(self.main_frame)
            self.lang_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
            ttk.Label(self.lang_frame, text=LANGUAGES[self.lang]["select_lang"], font=("Arial", self.font_size)).pack()
            ttk.Button(self.lang_frame, text="English", command=lambda: self.set_language("English")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Français", command=lambda: self.set_language("French")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Deutsch", command=lambda: self.set_language("German")).pack(side=tk.LEFT, padx=5)
            ttk.Button(self.lang_frame, text="Lëtzebuergesch", command=lambda: self.set_language("Luxembourgish")).pack(side=tk.LEFT, padx=5)

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        except Exception as e:
            logging.error(f"Initialization failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start application: {str(e)}")
            self.root.destroy()

    def on_resize(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=self.canvas.winfo_width())

    def set_language(self, lang):
        self.lang = lang
        self.data["lang"] = lang
        self.root.title(LANGUAGES[self.lang]["title"])
        self.lang_frame.grid_forget()
        self.build_main_ui()

    def validate_number(self, input_str):
        if input_str == "":
            return True
        if self.lang in ["French", "German", "Luxembourgish"]:
            input_str = input_str.replace(",", ".")
        return bool(re.match(r"^\d*\.?\d*$", input_str))

    def validate_catches(self, input_str):
        if input_str == "":
            return True
        return bool(re.match(r"^\d+$", input_str))

    def validate_length(self, input_str):
        """Validate input length for club and remark (max 64 chars)."""
        return len(input_str) <= 64

    def check_event_details(self):
        if not self.event_name.get().strip() or not self.location.get().strip():
            messagebox.showerror("Error", LANGUAGES[self.lang]["event_error"])
            return False
        return True

    def build_main_ui(self):
        for widget in self.main_frame.winfo_children():
            if widget != self.logo_label:
                widget.destroy()

        self.main_frame.columnconfigure(0, weight=1, minsize=400)
        self.main_frame.columnconfigure(1, weight=1, minsize=400)
        self.main_frame.rowconfigure(0, weight=0)
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=0)

        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)

        event_frame = ttk.LabelFrame(left_frame, text=LANGUAGES[self.lang]["event_details"], padding=5)
        event_frame.pack(fill="x")
        ttk.Label(event_frame, text=LANGUAGES[self.lang]["event_name"], font=("Arial", self.font_size)).grid(row=0, column=0, pady=3, sticky="w")
        self.event_name = ttk.Entry(event_frame, font=("Arial", self.font_size), width=20)
        self.event_name.grid(row=0, column=1, pady=3, sticky="ew")
        ttk.Label(event_frame, text=LANGUAGES[self.lang]["location"], font=("Arial", self.font_size)).grid(row=1, column=0, pady=3, sticky="w")
        self.location = ttk.Entry(event_frame, font=("Arial", self.font_size), width=20)
        self.location.grid(row=1, column=1, pady=3, sticky="ew")
        ttk.Label(event_frame, text=LANGUAGES[self.lang]["date"], font=("Arial", self.font_size)).grid(row=2, column=0, pady=3, sticky="w")
        self.date = DateEntry(event_frame, font=("Arial", self.font_size), date_pattern="dd/mm/yyyy", width=12)
        self.date.grid(row=2, column=1, pady=3, sticky="w")
        self.date.set_date(datetime.now())
        if self.data["event"]:
            self.event_name.insert(0, self.data["event"].get("name", ""))
            self.location.insert(0, self.data["event"].get("location", ""))
            date_str = self.data["event"].get("date", datetime.now().strftime("%d/%m/%Y"))
            try:
                self.date.set_date(date_str)
            except ValueError:
                self.date.set_date(datetime.now())
            self.event_name.config(state="disabled")
            self.location.config(state="disabled")
            self.date.config(state="disabled")

        catch_frame = ttk.LabelFrame(left_frame, text=LANGUAGES[self.lang]["log_catch"], padding=5)
        catch_frame.pack(fill="x", pady=5)
        ttk.Label(catch_frame, text=LANGUAGES[self.lang]["name"], font=("Arial", self.font_size)).grid(row=0, column=0, pady=3, sticky="w")
        self.catch_name_var = tk.StringVar()
        self.catch_name = ttk.Combobox(catch_frame, textvariable=self.catch_name_var, values=sorted(self.data["participants"].keys(), key=str.lower), font=("Arial", self.font_size), width=15)
        self.catch_name.grid(row=0, column=1, pady=3, sticky="ew")
        hint_text = LANGUAGES[self.lang]["select_participant"]
        self.catch_name_var.set(hint_text)
        self.catch_name.config(foreground='grey')
        self.catch_name.bind("<FocusIn>", self.on_combobox_focus_in)
        self.catch_name.bind("<FocusOut>", self.on_combobox_focus_out)
        self.catch_name.bind("<<ComboboxSelected>>", self.on_combobox_selected)
        self.add_btn = ttk.Button(catch_frame, text=LANGUAGES[self.lang]["add_participant"], command=self.open_add_participant_dialog)
        self.add_btn.grid(row=0, column=2, padx=10, pady=3)  # Increased padx for spacing
        ttk.Label(catch_frame, text=LANGUAGES[self.lang]["fish_weight"], font=("Arial", self.font_size)).grid(row=1, column=0, pady=3, sticky="w")
        self.fish_weight = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=15, validate="key", validatecommand=(self.root.register(self.validate_number), "%P"))
        self.fish_weight.grid(row=1, column=1, pady=3, sticky="ew")
        ttk.Label(catch_frame, text=LANGUAGES[self.lang]["num_catches"], font=("Arial", self.font_size)).grid(row=2, column=0, pady=3, sticky="w")
        self.num_catches = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=15, validate="key", validatecommand=(self.root.register(self.validate_catches), "%P"))
        self.num_catches.grid(row=2, column=1, pady=3, sticky="ew")
        self.num_catches.insert(0, "1")
        ttk.Label(catch_frame, text=LANGUAGES[self.lang]["fish_length"], font=("Arial", self.font_size)).grid(row=3, column=0, pady=3, sticky="w")
        self.fish_length = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=15, validate="key", validatecommand=(self.root.register(self.validate_number), "%P"))
        self.fish_length.grid(row=3, column=1, pady=3, sticky="ew")
        ttk.Label(catch_frame, text=LANGUAGES[self.lang]["fish_type"], font=("Arial", self.font_size)).grid(row=4, column=0, pady=3, sticky="w")
        self.fish_type = ttk.Entry(catch_frame, font=("Arial", self.font_size), width=15)
        self.fish_type.grid(row=4, column=1, pady=3, sticky="ew")
        self.log_btn = ttk.Button(catch_frame, text=LANGUAGES[self.lang]["log_catch"], command=self.log_catch)
        self.log_btn.grid(row=5, column=1, pady=5, sticky="e")

        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=3, pady=3)

        rankings_frame = ttk.LabelFrame(right_frame, text=LANGUAGES[self.lang]["live_rankings"], padding=5)
        rankings_frame.pack(fill="both", expand=True)
        self.rankings = ttk.Label(rankings_frame, text=self.get_rankings(), font=("Arial", self.font_size-2), justify="left", wraplength=400)
        self.rankings.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(rankings_frame)
        btn_frame.pack(fill="x", pady=3)
        self.report_btn = ttk.Button(btn_frame, text=LANGUAGES[self.lang]["generate_report"], command=self.generate_report)
        self.report_btn.pack(side=tk.LEFT, padx=3)
        self.reset_btn = ttk.Button(btn_frame, text=LANGUAGES[self.lang]["reset_event"], command=self.reset_event)
        self.reset_btn.pack(side=tk.LEFT, padx=3)
        self.export_btn = ttk.Button(btn_frame, text=LANGUAGES[self.lang]["export_event"], command=self.export_event)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        self.import_btn = ttk.Button(btn_frame, text=LANGUAGES[self.lang]["import_event"], command=self.import_event)
        self.import_btn.pack(side=tk.LEFT, padx=3)
        self.help_btn = ttk.Button(btn_frame, text=LANGUAGES[self.lang]["help"], command=self.show_help)
        self.help_btn.pack(side=tk.LEFT, padx=3)

        participants_frame = ttk.LabelFrame(right_frame, text=LANGUAGES[self.lang]["participants"], padding=5)
        participants_frame.pack(fill="x", pady=3)
        participants_canvas = tk.Canvas(participants_frame)
        participants_scrollbar = ttk.Scrollbar(participants_frame, orient="vertical", command=participants_canvas.yview)
        self.participants_list = tk.Text(participants_canvas, height=8, width=25, font=("Arial", self.font_size-2))
        participants_canvas.configure(yscrollcommand=participants_scrollbar.set)
        participants_scrollbar.pack(side="right", fill="y")
        participants_canvas.pack(side="left", fill="both", expand=True)
        participants_canvas.create_window((0, 0), window=self.participants_list, anchor="nw")
        self.participants_list.bind("<Configure>", lambda e: participants_canvas.configure(scrollregion=participants_canvas.bbox("all")))
        self.update_participants_list()

        footer_frame = ttk.Frame(self.main_frame)
        footer_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="s")
        footer_text = LANGUAGES[self.lang]["copyright"].split("fescherfrenn@outlook.com")[0]
        ttk.Label(footer_frame, text=footer_text, font=("Arial", self.font_size-4)).pack(side=tk.LEFT)
        email_label = tk.Label(footer_frame, text="fescherfrenn@outlook.com", font=("Arial", self.font_size-4), foreground="blue", cursor="hand2")
        email_label.pack(side=tk.LEFT)
        email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))
        ttk.Label(footer_frame, text=LANGUAGES[self.lang]["copyright"].split("fescherfrenn@outlook.com")[1], font=("Arial", self.font_size-4)).pack(side=tk.LEFT)

        self.create_tooltip(self.add_btn, LANGUAGES[self.lang]["tooltip_add"])
        self.create_tooltip(self.log_btn, LANGUAGES[self.lang]["tooltip_log"])
        self.create_tooltip(self.report_btn, LANGUAGES[self.lang]["tooltip_report"])
        self.create_tooltip(self.reset_btn, LANGUAGES[self.lang]["tooltip_reset"])
        self.create_tooltip(self.export_btn, LANGUAGES[self.lang]["tooltip_export"])
        self.create_tooltip(self.import_btn, LANGUAGES[self.lang]["tooltip_import"])
        self.create_tooltip(self.help_btn, LANGUAGES[self.lang]["tooltip_help"])

    def on_combobox_focus_in(self, event):
        if self.catch_name_var.get() == LANGUAGES[self.lang]["select_participant"]:
            self.catch_name_var.set('')
            self.catch_name.config(foreground='black')

    def on_combobox_focus_out(self, event):
        if not self.catch_name_var.get():
            self.catch_name_var.set(LANGUAGES[self.lang]["select_participant"])
            self.catch_name.config(foreground='grey')

    def on_combobox_selected(self, event):
        self.catch_name.config(foreground='black')

    def open_add_participant_dialog(self):
        if not self.check_event_details():
            return

        dialog = Toplevel(self.root)
        dialog.title(LANGUAGES[self.lang]["add_participant"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("400x300")

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=LANGUAGES[self.lang]["name"], font=("Arial", self.font_size)).grid(row=0, column=0, sticky="w", pady=3)
        name_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=20)
        name_entry.grid(row=0, column=1, pady=3, sticky="ew")
        name_entry.focus_set()

        ttk.Label(frame, text=LANGUAGES[self.lang]["club"], font=("Arial", self.font_size)).grid(row=1, column=0, sticky="w", pady=3)
        club_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=20, validate="key", validatecommand=(self.root.register(self.validate_length), "%P"))
        club_entry.grid(row=1, column=1, pady=3, sticky="ew")

        ttk.Label(frame, text=LANGUAGES[self.lang]["category"], font=("Arial", self.font_size)).grid(row=2, column=0, sticky="w", pady=3)
        category_options = list(LANGUAGES[self.lang]["category_options"].values())
        category_combobox = ttk.Combobox(frame, font=("Arial", self.font_size), width=18, values=category_options, state="readonly")
        category_combobox.grid(row=2, column=1, pady=3, sticky="ew")
        category_combobox.set("")

        ttk.Label(frame, text=LANGUAGES[self.lang]["remark"], font=("Arial", self.font_size)).grid(row=3, column=0, sticky="w", pady=3)
        remark_entry = ttk.Entry(frame, font=("Arial", self.font_size), width=20, validate="key", validatecommand=(self.root.register(self.validate_length), "%P"))
        remark_entry.grid(row=3, column=1, pady=3, sticky="ew")

        def add():
            name = name_entry.get().strip()
            club = club_entry.get().strip()[:64]
            category = LANGUAGES[self.lang]["category_options"].get(category_combobox.get(), "")
            remark = remark_entry.get().strip()[:64]
            if not name:
                messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
                return
            if name in self.data["participants"]:
                messagebox.showerror("Error", LANGUAGES[self.lang]["duplicate_name"])
                return
            self.data["participants"][name] = {
                "id": len(self.data["participants"]) + 1,
                "club": club,
                "category": category,
                "remark": remark
            }
            self.data["catches"][name] = []
            self.catch_name["values"] = sorted(self.data["participants"].keys(), key=str.lower)
            self.update_participants_list()
            self.update_event()
            messagebox.showinfo("Success", LANGUAGES[self.lang]["saved"])
            dialog.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text=LANGUAGES[self.lang]["add_participant"], command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=LANGUAGES[self.lang]["close"], command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        dialog.bind("<Return>", lambda e: add())

    def create_tooltip(self, widget, text):
        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry("+0+0")
        label = ttk.Label(tooltip, text=text, background="lightyellow", relief="solid", borderwidth=1)
        label.pack()
        tooltip.withdraw()

        def show(event):
            x, y = event.widget.winfo_rootx() + 20, event.widget.winfo_rooty() + 20
            tooltip.wm_geometry(f"+{x}+{y}")
            tooltip.deiconify()

        def hide(event):
            tooltip.withdraw()

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def show_help(self):
        help_window = Toplevel(self.root)
        help_window.title(LANGUAGES[self.lang]["help"])
        help_window.geometry("600x400")
        help_window.transient(self.root)
        help_window.grab_set()

        canvas = tk.Canvas(help_window)
        scrollbar = ttk.Scrollbar(help_window, orient="vertical", command=canvas.yview)
        help_frame = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.create_window((0, 0), window=help_frame, anchor="nw")
        help_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(help_frame, text=LANGUAGES[self.lang]["help_manual"], font=("Arial", self.font_size-2), wraplength=550, justify="left").pack(padx=5, pady=5)
        email_label = tk.Label(help_frame, text="fescherfrenn@outlook.com", font=("Arial", self.font_size-2), foreground="blue", cursor="hand2")
        email_label.pack(anchor="w", padx=5)
        email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:fescherfrenn@outlook.com"))

        close_btn = ttk.Button(help_frame, text=LANGUAGES[self.lang]["close"], command=help_window.destroy)
        close_btn.pack(pady=5)
        help_window.bind("<Return>", lambda e: help_window.destroy())

    def update_participants_list(self):
        if self.participants_list:
            self.participants_list.config(state="normal")
            self.participants_list.delete(1.0, tk.END)
            for i, name in enumerate(sorted(self.data["participants"].keys(), key=str.lower), 1):
                self.participants_list.insert(tk.END, f"{i}. {name}\n")
            self.participants_list.config(state="disabled")

    def log_catch(self):
        if not self.check_event_details():
            return
        name = self.catch_name_var.get().strip()
        fish_type = self.fish_type.get().strip()
        num_catches_str = self.num_catches.get()
        try:
            weight_str = self.fish_weight.get()
            length_str = self.fish_length.get()
            if not weight_str or float(weight_str.replace(",", ".")) <= 0:
                messagebox.showerror("Error", LANGUAGES[self.lang]["invalid_number"])
                return
            if not num_catches_str or int(num_catches_str) < 1:
                messagebox.showerror("Error", LANGUAGES[self.lang]["invalid_catches"])
                return
            if name == LANGUAGES[self.lang]["select_participant"] or not name:
                messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
                return
            if name not in self.data["participants"]:
                messagebox.showerror("Error", LANGUAGES[self.lang]["duplicate_name"])
                return
            weight = float(weight_str.replace(",", "."))
            num_catches = int(num_catches_str)
            length = float(length_str.replace(",", ".")) if length_str and float(length_str.replace(",", ".")) > 0 else None
            if num_catches > 1:
                fish_type = ""
                length = None
            if name in self.data["participants"] and weight > 0:
                catch = {"weight": weight, "length": length, "type": fish_type, "time": datetime.now().strftime("%H:%M"), "num_catches": num_catches}
                self.data["catches"][name].append(catch)
                self.fish_type.delete(0, tk.END)
                self.fish_weight.delete(0, tk.END)
                self.fish_length.delete(0, tk.END)
                self.num_catches.delete(0, tk.END)
                self.num_catches.insert(0, "1")
                self.catch_name_var.set('')
                self.on_combobox_focus_out(None)  # Reset to hint
                self.rankings.config(text=self.get_rankings())
                self.update_event()
                messagebox.showinfo("Success", LANGUAGES[self.lang]["saved"])
            else:
                messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
        except ValueError:
            messagebox.showerror("Error", LANGUAGES[self.lang]["invalid_number"])

    def update_event(self):
        self.data["event"] = {"name": self.event_name.get(), "location": self.location.get(), "date": self.date.get()}
        if all(self.data["event"].values()):
            self.event_name.config(state="disabled")
            self.location.config(state="disabled")
            self.date.config(state="disabled")
        try:
            save_data(self.data, self.data["event"])
        except Exception as e:
            logging.error(f"update_event failed: {str(e)}")
            messagebox.showerror("Error", LANGUAGES[self.lang]["error"])

    def get_rankings(self):
        rankings = f"{LANGUAGES[self.lang]['live_rankings']}:\n\n"
        total_weights = {name: sum(c["weight"] for c in catches) for name, catches in self.data["catches"].items()}
        top_weights = sorted(total_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        rankings += f"{LANGUAGES[self.lang]['total_weight']}:\n"
        for i, (name, weight) in enumerate(top_weights, 1):
            rankings += f"{i}. {name}: {weight:.2f} kg\n"
        all_catches = [(name, catch) for name, catches in self.data["catches"].items() for catch in catches if catch["num_catches"] == 1]
        top_lengths = sorted(all_catches, key=lambda x: x[1]["length"] or 0, reverse=True)[:3]
        rankings += f"\n{LANGUAGES[self.lang]['longest_fish']}:\n"
        for i, (name, catch) in enumerate(top_lengths, 1):
            rankings += f"{i}. {name}: {catch['length'] or 0} cm\n"
        top_heaviest = sorted(all_catches, key=lambda x: x[1]["weight"], reverse=True)[:3]
        rankings += f"\n{LANGUAGES[self.lang]['heaviest_fish']}:\n"
        for i, (name, catch) in enumerate(top_heaviest, 1):
            rankings += f"{i}. {name}: {catch['weight']} kg\n"
        num_catches = {name: sum(c["num_catches"] for c in catches) for name, catches in self.data["catches"].items()}
        top_catches = sorted(num_catches.items(), key=lambda x: x[1], reverse=True)[:3]
        rankings += f"\n{LANGUAGES[self.lang]['num_catches_label']}:\n"
        for i, (name, count) in enumerate(top_catches, 1):
            rankings += f"{i}. {name}: {count} catches\n"
        return rankings

    def generate_report(self):
        if not self.data["participants"]:
            messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
            return
        try:
            event = self.data["event"]
            event_name_file = str(event.get("name", "event")).replace(" ", "_")
            event_name_display = str(event.get("name", "event"))
            event_date = str(event.get("date", datetime.now().strftime("%d/%m/%Y")))
            date_obj = datetime.strptime(event_date, "%d/%m/%Y")
            date_str = date_obj.strftime("%Y%m%d")
            folder_name = f"{date_str}_{event_name_file}"
            filename = f"{folder_name}/{folder_name}.pdf"

            try:
                os.makedirs(folder_name, exist_ok=True)
            except PermissionError:
                messagebox.showerror("Error", LANGUAGES[self.lang]["permission_error"].replace("[folder]", folder_name))
                return

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            bold_style = styles["BodyText"]
            bold_style.fontName = "Helvetica-Bold"
            normal_style = styles["BodyText"]
            center_style = styles["Heading2"]
            center_style.alignment = 1
            story = []

            logo_path = "logo.png"
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=1*inch, height=1*inch)
                logo.hAlign = "LEFT"
                story.append(logo)
                story.append(Spacer(1, 12))

            event_location = str(event.get("location", "Unknown Location"))
            story.append(Paragraph(LANGUAGES[self.lang]["summary_report"], styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", center_style))
            story.append(Spacer(1, 12))

            data_table = [[
                Paragraph("#", normal_style),
                Paragraph(LANGUAGES[self.lang]["name"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_club"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_category"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_remark"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_participants"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_total_weight"], normal_style),
                Paragraph(LANGUAGES[self.lang]["table_longest_fish"], normal_style)
            ]]
            total_weights = {name: sum(c["weight"] for c in catches) for name, catches in self.data["catches"].items()}
            sorted_participants = sorted(total_weights.items(), key=lambda x: x[1], reverse=True)
            for i, (name, _) in enumerate(sorted_participants, 1):
                catches = self.data["catches"][name]
                total_catches = sum(c["num_catches"] for c in catches) if catches else 0
                total_weight = sum(c["weight"] for c in catches) if catches else 0
                longest = max((c["length"] for c in catches if c["length"] is not None), default=0) if catches else 0
                weight_str = f"{total_weight:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if self.lang in ["French", "German", "Luxembourgish"] else f"{total_weight:.2f}"
                participant_info = self.data["participants"][name]
                club = participant_info.get("club", "")
                category = participant_info.get("category", "")
                remark = participant_info.get("remark", "")
                data_table.append([
                    Paragraph(str(i), normal_style),
                    Paragraph(str(name), normal_style),
                    Paragraph(club, normal_style),
                    Paragraph(category, normal_style),
                    Paragraph(remark, normal_style),
                    Paragraph(str(total_catches), normal_style),
                    Paragraph(weight_str, normal_style),
                    Paragraph(f"{longest}", normal_style)
                ])
            story.append(Table(data_table, colWidths=[30, 100, 80, 80, 80, 60, 60, 60], style=[
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('LEADING', (0,0), (-1,-1), 12),
                ('WORDWRAP', (0,0), (-1,-1), 'CJK')
            ]))
            story.append(Spacer(1, 12))

            total_participants = len(self.data["participants"])
            total_catches = sum(sum(c["num_catches"] for c in catches) for catches in self.data["catches"].values())
            total_event_weight = sum(sum(c["weight"] for c in catches) for catches in self.data["catches"].values())
            weight_str = f"{total_event_weight:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if self.lang in ["French", "German", "Luxembourgish"] else f"{total_event_weight:.2f}"
            summary_text = f"{LANGUAGES[self.lang]['summary']} {total_participants} {LANGUAGES[self.lang]['summary_participants']}, {total_catches} {LANGUAGES[self.lang]['summary_total_catches']}, {weight_str} {LANGUAGES[self.lang]['summary_total_weight']}"
            story.append(Paragraph(summary_text, styles["Normal"]))
            story.append(PageBreak())

            for rank, (name, _) in enumerate(sorted_participants, 1):
                catches = sorted(self.data["catches"][name], key=lambda x: x["time"]) if self.data["catches"][name] else []
                if not catches:
                    continue
                story.append(Paragraph(f"{event_name_display} - {event_location} - {event_date}", styles["Title"]))
                story.append(Paragraph(name, styles["Title"]))
                story.append(Spacer(1, 12))
                catch_table = [[
                    Paragraph(LANGUAGES[self.lang]["indiv_time"], normal_style),
                    Paragraph(LANGUAGES[self.lang]["indiv_type"], normal_style),
                    Paragraph(LANGUAGES[self.lang]["number_of_catches"], normal_style),
                    Paragraph(LANGUAGES[self.lang]["indiv_weight"], normal_style),
                    Paragraph(LANGUAGES[self.lang]["indiv_length"], normal_style)
                ]]
                for catch in catches:
                    fish_type = catch.get("type", "Unknown")
                    weight_val = catch["weight"]
                    weight_str = f"{weight_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if self.lang in ["French", "German", "Luxembourgish"] else f"{weight_val:.2f}"
                    weight_par = Paragraph(weight_str, bold_style) if catch == max(catches, key=lambda x: x["weight"]) else Paragraph(weight_str, normal_style)
                    length_val = Paragraph(str(catch["length"]) if catch["length"] is not None else "", bold_style if catch["length"] == max((c["length"] or 0 for c in catches if c["length"] is not None), default=0) else normal_style)
                    catch_table.append([
                        Paragraph(str(catch["time"]), normal_style),
                        Paragraph(str(fish_type), normal_style),
                        Paragraph(str(catch["num_catches"]), normal_style),
                        weight_par,
                        length_val
                    ])
                story.append(Table(catch_table, colWidths=[60, 80, 60, 60, 60], style=[
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('LEADING', (0,0), (-1,-1), 12),
                    ('WORDWRAP', (0,0), (-1,-1), 'CJK')
                ]))
                story.append(Spacer(1, 12))
                participant_info = self.data["participants"][name]
                if participant_info.get("club"):
                    story.append(Paragraph(f"{LANGUAGES[self.lang]['club']} {participant_info['club']}", styles["Normal"]))
                if participant_info.get("category"):
                    story.append(Paragraph(f"{LANGUAGES[self.lang]['category']} {participant_info['category']}", styles["Normal"]))
                if participant_info.get("remark"):
                    story.append(Paragraph(f"{LANGUAGES[self.lang]['remark']} {participant_info['remark']}", styles["Normal"]))
                total_catches = sum(c["num_catches"] for c in catches)
                total_weight = sum(c["weight"] for c in catches)
                weight_str = f"{total_weight:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if self.lang in ["French", "German", "Luxembourgish"] else f"{total_weight:.2f}"
                story.append(Paragraph(f"{LANGUAGES[self.lang]['indiv_total_catches']}: {total_catches}", styles["Normal"]))
                story.append(Paragraph(f"{LANGUAGES[self.lang]['indiv_total_weight']}: {weight_str} kg", styles["Normal"]))
                story.append(Paragraph(f"{LANGUAGES[self.lang]['indiv_final_rank']}: {rank}", styles["Normal"]))
                story.append(PageBreak())

            def add_footer(canvas, doc):
                canvas.saveState()
                canvas.setFont("Helvetica", 10)
                footer_text = LANGUAGES[self.lang]["copyright"].replace(
                    "fescherfrenn@outlook.com",
                    '<link href="mailto:fescherfrenn@outlook.com" color="blue">fescherfrenn@outlook.com</link>'
                )
                p = Paragraph(footer_text, normal_style)
                w, h = p.wrap(doc.width, doc.bottomMargin)
                p.drawOn(canvas, doc.leftMargin, doc.bottomMargin - h - 10)
                canvas.restoreState()

            doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
            messagebox.showinfo("Success", LANGUAGES[self.lang]["report_generated"].replace("[date]_[event_name]", f"{date_str}_{event_name_file}"))
        except Exception as e:
            logging.error(f"generate_report failed: {str(e)}")
            messagebox.showerror("Error", f"Report generation failed: {type(e).__name__}: {str(e)}")

    def custom_dialog(self, title, message, buttons):
        dialog = Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        text_length = len(message)
        width = max(300, min(600, text_length * 8))
        height = max(150, 100 + (text_length // 50) * 30)
        dialog.geometry(f"{int(width)}x{int(height)}")

        label = ttk.Label(dialog, text=message, wraplength=width-20, font=("Arial", self.font_size))
        label.pack(pady=10, padx=10)
        
        result = [None]
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=5, side=tk.BOTTOM)
        for btn_text, value in buttons:
            btn = ttk.Button(btn_frame, text=btn_text, command=lambda v=value: [result.__setitem__(0, v), dialog.destroy()])
            btn.pack(side=tk.LEFT, padx=5)
            if btn_text == LANGUAGES[self.lang]["yes"]:
                btn.focus_set()
                dialog.bind("<Return>", lambda e, v=value: [result.__setitem__(0, v), dialog.destroy()])

        dialog.wait_window()
        return result[0]

    def reset_event(self):
        if self.custom_dialog(LANGUAGES[self.lang]["reset_event"], LANGUAGES[self.lang]["confirm_reset"], [(LANGUAGES[self.lang]["yes"], True), (LANGUAGES[self.lang]["no"], False)]):
            self.data = {"event": {}, "participants": {}, "catches": {}, "lang": self.lang, "version": APP_VERSION}
            folder_name = get_event_folder(self.data["event"])
            data_file = os.path.join(folder_name, f"{folder_name}.json")
            if os.path.exists(data_file):
                try:
                    os.remove(data_file)
                except Exception as e:
                    logging.error(f"reset_event file removal failed: {str(e)}")
            if os.path.exists(TEMP_DATA_FILE):
                try:
                    os.remove(TEMP_DATA_FILE)
                except Exception as e:
                    logging.error(f"reset_event temp file removal failed: {str(e)}")
            self.build_main_ui()
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["reset_success"])

    def export_event(self):
        event = self.data["event"]
        folder_name = get_event_folder(event)
        filename = os.path.join(folder_name, f"{folder_name}.json")

        try:
            os.makedirs(folder_name, exist_ok=True)
        except PermissionError:
            messagebox.showerror("Error", LANGUAGES[self.lang]["permission_error"].replace("[folder]", folder_name))
            return

        try:
            with open(filename, 'w') as file:
                json.dump(self.data, file, indent=4)
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["export_success"].format(filename=filename))
        except Exception as e:
            logging.error(f"export_event failed: {str(e)}")
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def import_event(self):
        try:
            file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
            if not file_path:
                return
            with open(file_path, 'r') as file:
                imported_data = json.load(file)
        
            if not isinstance(imported_data, dict) or "event" not in imported_data or "participants" not in imported_data:
                raise ValueError("Invalid event data format")
        
            # Ensure new fields for backward compatibility
            for name in imported_data["participants"]:
                if not isinstance(imported_data["participants"][name], dict):
                    imported_data["participants"][name] = {
                        "id": imported_data["participants"][name],
                        "club": "",
                        "category": "",
                        "remark": ""
                    }
            self.data = imported_data
            self.root.title(LANGUAGES[self.lang]["title"])
            self.build_main_ui()
            messagebox.showinfo(LANGUAGES[self.lang]["saved"], LANGUAGES[self.lang]["import_success"])
        except Exception as e:
            logging.error(f"import_event failed: {str(e)}")
            messagebox.showerror(LANGUAGES[self.lang]["error"], f"Failed to import event: {str(e)}")

    def on_closing(self):
        if self.custom_dialog(LANGUAGES[self.lang]["close"], LANGUAGES[self.lang]["confirm_close"], [(LANGUAGES[self.lang]["yes"], True), (LANGUAGES[self.lang]["no"], False)]):
            try:
                save_data(self.data, self.data["event"])
            except Exception as e:
                logging.error(f"on_closing save failed: {str(e)}")
                messagebox.showerror("Error", LANGUAGES[self.lang]["error"])
            self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FishingApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Main loop error: {str(e)}")
        messagebox.showerror("Error", f"Application failed: {str(e)}")

