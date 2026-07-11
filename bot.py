import discord
from discord.ext import commands, tasks
import random
import os
import json
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta

app = Flask('')

@app.route('/')
def home(): return "Le bot de Madagascar est vivant !"

def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

FILE_NAME = "missions.txt"
PROFILES_FILE = "profils.txt"
STATS_GLOBAL_FILE = "stats_globales.txt"

def charger_missions_fichier():
    structure = {"commune": [], "moyenne": [], "difficile": [], "royal": []}
    if not os.path.exists(FILE_NAME): return structure
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line: continue
            cat, texte, delai = line.split("|", 2)
            if cat in structure: structure[cat].append({"texte": texte, "delai": delai})
    return structure

def réécrire_toutes_missions(structure):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        for cat, liste in structure.items():
            for m in liste: f.write(f"{cat}|{m['texte']}|{m['delai']}\n")

def sauvegarder_mission_fichier(categorie, texte, delai):
    with open(FILE_NAME, "a", encoding="utf-8") as f: f.write(f"{categorie}|{texte}|{delai}\n")

def charger_profils():
    if not os.path.exists(PROFILES_FILE): return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def sauvegarder_profils(profils):
    with open(PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(profils, f, indent=4, ensure_ascii=False)

def charger_stats_globales():
    if not os.path.exists(STATS_GLOBAL_FILE): return {"urgences_reussies": 0, "urgences_echouees": 0}
    try:
        with open(STATS_GLOBAL_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"urgences_reussies": 0, "urgences_echouees": 0}

def sauvegarder_stats_globales(stats):
    with open(STATS_GLOBAL_FILE, "w", encoding="utf-8") as f: json.dump(stats, f, indent=4)

def initialiser_profil(p_id, profils):
    s_id = str(p_id)
    if s_id not in profils:
        profils[s_id] = {
            "reussies": {"commune": 0, "moyenne": 0, "difficile": 0, "royal": 0, "urgence": 0},
            "echouees": {"commune": 0, "moyenne": 0, "difficile": 0, "royal": 0, "urgence": 0},
            "historique": []
        }
    if "urgence" not in profils[s_id]["reussies"]: profils[s_id]["reussies"]["urgence"] = 0
    if "urgence" not in profils[s_id]["echouees"]: profils[s_id]["echouees"]["urgence"] = 0

def ajouter_historique(p_id, profils, texte, statut):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    hist = profils[s_id]["historique"]
    hist.insert(0, {"texte": texte, "statut": statut, "date": datetime.now().strftime("%d/%m/%Y")})
    profils[s_id]["historique"] = hist[:5]

def calculer_rang(stats):
    r = stats["reussies"]
    if r["commune"] >= 20 and r["moyenne"] >= 10 and r["difficile"] >= 5 and r["royal"] >= 1:
        return "👑 Légende de Madagascar"
    if r["commune"] >= 10 and r["moyenne"] >= 5 and r["difficile"] >= 1:
        return "⚔️ Vétéran"
    if r["commune"] >= 5:
        return "🛡️ Soldat"
    return "🔰 Recrue"

def extraire_duree(delai_texte):
    mots = delai_texte.lower().replace("pour dans", "").replace("pour", "").strip().split()
    valeur = 1
    for i, mot in enumerate(mots):
        try: valeur = float(mots[i-1].replace(",", "."))
        except (ValueError, IndexError): continue
        if "min" in mot or "mn" in mot: return timedelta(minutes=valeur)
        if "heure" in mot or "hour" in mot or "h" in mot: return timedelta(hours=valeur)
        if "jour" in mot or "day" in mot or "j" in mot: return timedelta(days=valeur)
        if "semaine" in mot or "week" in mot: return timedelta(weeks=valeur)
        if "mois" in mot or "moi" in mot or "month" in mot: return timedelta(days=valeur * 30)
    return timedelta(days=3)

missions_dispo = charger_missions_fichier()
missions_actives = {}
urgence_active = {}

TEXTE_ECHEC = (
    "⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖊 𝕸𝖆𝖉𝖆𝖈𝖆𝖘𝖈𝖆𝖗** ⚜️\n"
    "**D'après l'article Ⅴ — Rappel :**\n"
    "- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
    "- *L'État récompense l'investissement et la persévérance.*\n"
    "- *Les missions constituent l'un des principaux moyens de progresser au sein de Madagascar.*"
)

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    global urgence_active
    maintenant = datetime.now()
    
    if urgence_active and not urgence_active.get("en_attente", False):
        date_fin_urg = urgence_active["date_fin"]
        channel_urg = bot.get_channel(urgence_active["channel_id"])
        
        if maintenant > date_fin_urg:
            st_g = charger_stats_globales()
            st_g["urgences_echouees"] += 1
            savgarder_stats_globales(st_g)
            
            profils = charger_profils()
            for uid in urgence_active["membres"]:
                initialiser_profil(uid, profils)
                profils[str(uid)]["echouees"]["urgence"] += 1
                ajouter_historique(uid, profils, f"[URGENCE] {urgence_active['texte']}", "Échec")
            sauvegarder_profils(profils)
            
            if channel_urg:
                mentions = ", ".join([f"<@{uid}>" for uid in urgence_active["membres"]]) if urgence_active["membres"] else "Personne"
                await channel_urg.send(
                    f"🚨 **CRISE NATIONALE SUR MOCHA — MADAGASCAR** 🚨\n"
                    f"Le délai du décret d'urgence est dépassé ! L'objectif a échoué.\n"
                    f"Citoyens impactés : {mentions}\n"
                    f"📉 *La réputation et l'organisation du pays en pâtissent.*"
                )
            urgence_active = {}
            
    missions_a_retirer = []
    for leader_id, m_info in list(missions_actives.items()):
        if m_info.get("traité_ce_cycle", False): continue
        if m_info.get("en_attente", False): continue
        
        channel = bot.get_channel(m_info["channel_id"])
        if not channel: continue
        
        escouade = m_info["membres"]
        mentions_membres = ", ".join([f"<@{uid}>" for uid in escouade])
        duree_totale = m_info["duree_totale"]
        date_debut = m_info["date_debut"]
        date_fin = m_info["date_fin"]
        temps_restant = date_fin - maintenant
        temps_ecoule = maintenant - date_debut

        for uid in escouade:
            if uid in missions_actives: missions_actives[uid]["traité_ce_cycle"] = True

        if maintenant > date_fin:
            missions_a_retirer.append(leader_id)
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            profils = charger_profils()
            for uid in escouade:
                initialiser_profil(uid, profils)
                profils[str(uid)]["echouees"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            role_instructeur = discord.utils.get(channel.guild.roles, name="Instructeur")
            await channel.send(
                f"🚨 **MISSION ÉCHOUÉE** 🚨\nLe temps imparti est écoulé ! La mission de ({mentions_membres}) a échoué.\n"
                f"📢 {role_instructeur.mention if role_instructeur else '@Instructeur'}, des citoyens ont failli à leur devoir.\n\n{TEXTE_ECHEC}"
            )
        elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
            m_info["alerte_un_quart"] = True
            m_info["alerte_moitie"] = True
            jours = temps_restant.days
            heures, reste = divmod(temps_restant.seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            await channel.send(f"⏳ **CRITIQUE** {mentions_membres} : -25% du temps restant ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
        elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
            m_info["alerte_moitie"] = True
            await channel.send(f"🌗 **MI-PARCOURS** {mentions_membres} : la moitié du temps s'est écoulée !")

    for uid, m_info in list(missions_actives.items()):
        if "traité_ce_cycle" in m_info: del m_info["traité_ce_cycle"]
    for leader_id in missions_a_retirer:
        if leader_id in missions_actives:
            escouade = missions_actives[leader_id]["membres"]
            for uid in escouade:
                if uid in missions_actives: del missions_actives[uid]

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    print("Bot MADAmission Pro — Retour de mission activé pour Madagascar !")

@bot.event
async def on_message(message):
    global missions_dispo, urgence_active
    if message.author.bot: return
    content = message.content.strip()
    content_lower = content.lower()

    # --- ENCADREMENT DU !AIDE / !HELP ---
    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DE MADAGASCAR ⚜️", color=discord.Color.gold())
        
        citoyen_desc = (
            "⚔️ **SYSTÈME DE QUÊTES COMPLET**\n"
            "`!mission <difficulté>`\n↳ Pioche une mission en solo (`commune`, `moyenne`, `difficile`, `royal`).\n\n"
            "`!mission_groupe <difficulté> @joueur1...`\n↳ Déclenche une mission collective avec ton escouade.\n\n"
            "`!rejoindre_urgence`\n↳ Prends les armes et inscris-toi sur le décret d'urgence national.\n\n"
            "`!fin`\n↳ Met le chrono en pause et alerte les Instructeurs pour vérification.\n\n"
            "`!missions_en_cours`\n↳ Affiche le statut de toutes les tâches actives et de la crise.\n\n"
            "📊 **INFORMATIONS ET RANGS**\n"
            "`!profil [@joueur]`\n↳ Regarde ton rang, tes victoires, tes échecs et ton taux de réussite.\n\n"
            "`!historique`\n↳ Affiche le parchemin de tes 5 dernières actions accomplies.\n\n"
            "`!stats_royaume`\n↳ Regarde les statistiques globales de Madagascar (efficacité, réussite, crises)."
        )
        embed.add_field(name="👥 ESPACE DES CITOYENS", value=citoyen_desc, inline=False)
        
        if message.author.guild_permissions.administrator:
            admin_desc = (
                "🚨 **GESTION DE CRISE**\n"
                "`!urgence <texte> pour dans <délai>`\n↳ Proclame un état d'urgence chronométré (Ex: `pour dans 2h` ou `2 jours`).\n\n"
                "`!missionfinit @joueur`\n↳ Valide définitivement l'urgence ou la quête du joueur.\n\n"
                "`!missionechec @joueur`\n↳ Invalide la quête : elle retourne dans le panier et inflige 1 point de malus d'échec.\n\n"
                "🛠️ **AJUSTEMENTS DES COUNTERS**\n"
                "`!addpoints @joueur <difficulté> <reussies/echouees> <nombre>`\n↳ Ajoute manuellement des points à un membre.\n\n"
                "`!delpoints @joueur <difficulté> <reussies/echouees> <nombre>`\n↳ Retire des points du compteur d'un membre.\n\n"
                "📂 **BASE DE DONNÉES DES MISSIONS**\n"
                "`!listemissions`\n↳ Liste l'intégralité des quêtes enregistrées par catégorie.\n\n"
                "`!addmission <difficulté> <texte> pendant <temps>`\n↳ Enregistre un nouveau décret (Ex: `commune Miner du fer pendant 1h`).\n\n"
                "`!delmission <difficulté> <numéro>`\n↳ Supprime définitivement une quête via son numéro de liste."
            )
            embed.add_field(name="👑 HAUT COMMANDEMENT (ADMINISTRATEUR)", value=admin_desc, inline=False)
            
        await message.channel.send(embed=embed)
        return

    # --- COMMANDES D'AJUSTEMENT DE POINTS ---
    if content_lower.startswith("!addpoints"):
        if not message.author.guild_permissions.administrator: return
        mots = content.split()
        if len(mots) < 5 or not message.mentions:
            await message.channel.send("❌ Usage : `!addpoints @joueur <difficulté> <reussies/echouees> <quantité>`")
            return
        cible = message.mentions[0]
        cat = mots[2].lower()
        if cat in ["commun", "commune"]: cat = "commune"
        elif cat in ["moyen", "moyenne"]: cat = "moyenne"
        elif cat not in ["difficile", "royal", "urgence"]:
            await message.channel.send("❌ Catégorie invalide (`commune`, `moyenne`, `difficile`, `royal`, `urgence`).")
            return
        type_point = mots[3].lower()
        if type_point not in ["reussies", "reussie", "echouees", "echouee"]:
            await message.channel.send("❌ Choisis entre `reussies` ou `echouees`.")
            return
        if type_point == "reussie": type_point = "reussies"
        if type_point == "echouee": type_point = "echouees"
        try: qte = int(mots[4])
        except ValueError: return
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        profils[str(cible.id)][type_point][cat] += qte
        sauvegarder_profils(profils)
        ajouter_historique(cible.id, profils, f"Points ajoutés par l'administration (+{qte} {cat})", "Modif Admin")
        await message.channel.send(f"✅ Ajustement fait : `+{qte}` en {cat} ({type_point}) pour {cible.mention}.")
        return

    if content_lower.startswith("!delpoints"):
        if not message.author.guild_permissions.administrator: return
        mots = content.split()
        if len(mots) < 5 or not message.mentions:
            await message.channel.send("❌ Usage : `!delpoints @joueur <difficulté> <reussies/echouees> <quantité>`")
            return
        cible = message.mentions[0]
        cat = mots[2].lower()
        if cat in ["commun", "commune"]: cat = "commune"
        elif cat in ["moyen", "moyenne"]: cat = "moyenne"
        elif cat not in ["difficile", "royal", "urgence"]:
            await message.channel.send("❌ Catégorie invalide (`commune`, `moyenne`, `difficile`, `royal`, `urgence`).")
            return
        type_point = mots[3].lower()
        if type_point not in ["reussies", "reussie", "echouees", "echouee"]:
            await message.channel.send("❌ Choisis entre `reussies` ou `echouees`.")
            return
        if type_point == "reussie": type_point = "reussies"
        if type_point == "echouee": type_point = "echouees"
        try: qte = int(mots[4])
        except ValueError: return
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        actuel = profils[str(cible.id)][type_point][cat]
        nouveau = max(0, actuel - qte)
        profils[str(cible.id)][type_point][cat] = nouveau
        sauvegarder_profils(profils)
        ajouter_historique(cible.id, profils, f"Points retirés par l'administration (-{qte} {cat})", "Modif Admin")
        await message.channel.send(f"✅ Ajustement fait : Retrait de `{qte}` en {cat} ({type_point}) pour {cible.mention}.")
        return

    # --- ÉTAT DES MISSIONS ---
    if content_lower == "!missions_en_cours":
        msg = ""
        if urgence_active:
            statut_urg = "⏳ EN ATTENTE DE VALIDATION" if urgence_active.get("en_attente", False) else "⏱️ Temps restant"
            t_restant = urgence_active["date_fin"] - datetime.now()
            jours = max(0, t_restant.days)
            heures, reste = divmod(max(0, t_restant.seconds), 3600)
            minutes, _ = divmod(reste, 60)
            mentions = ", ".join([f"<@{uid}>" for uid in urgence_active["membres"]]) if urgence_active["membres"] else "Aucun volontaire"
            
            msg += f"🚨 **DÉCRET D'URGENCE NATIONAL — MADAGASCAR** 🚨\n"
            msg += f"📜 *\"{urgence_active['texte']}\"*\n"
            if urgence_active.get("en_attente", False):
                msg += f"🛑 **Chrono gelé** : En attente de l'Instructeur.\n"
            else:
                msg += f"{statut_urg} : `{jours}j {heures}h {minutes}m`\n"
            msg += f"👥 Volontaires : {mentions}\n\n"
        
        if not missions_actives:
            msg += "⚪ Aucune mission standard n'est active actuellement au sein du pays."
        else:
            msg += "⚜️ **MISSIONS STANDARDS :**\n"
            vus = set()
            for j_id, m in missions_actives.items():
                if id(m) in vus: continue
                vus.add(id(m))
                t_rest = m["date_fin"] - datetime.now()
                jours = max(0, t_rest.days)
                heures, reste = divmod(max(0, t_rest.seconds), 3600)
                minutes, _ = divmod(reste, 60)
                membres_txt = ", ".join([f"<@{uid}>" for uid in m["membres"]])
                
                if m.get("en_attente", False):
                    msg += f"👤 {membres_txt} [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* 🛑 **GELÉ (En attente d'évaluation)**\n"
                else:
                    msg += f"👤 {membres_txt} [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* (Reste : `{jours}j {heures}h {minutes}m`)\n"
        await message.channel.send(msg[:2000])
        return

    # --- COMMANDE URGENCE ---
    if content_lower.startswith("!urgence"):
        if not message.author.guild_permissions.administrator: return
        texte_total = content[9:].strip()
        if "pour dans" not in text_total.lower():
            await message.channel.send("❌ Format invalide. Exemple : `!urgence <texte> pour dans 2h`")
            return
        index_pour = texte_total.lower().rfind("pour dans")
        texte_urgence = texte_total[:index_pour].strip()
        delai_texte = texte_total[index_pour + 9:].strip()
        
        duree = extraire_duree(delai_texte)
        urgence_active = {
            "texte": texte_urgence, "date_fin": datetime.now() + duree,
            "channel_id": message.channel.id, "membres": [], "en_attente": False
        }
        await message.channel.send(f"🚨 **ALERTE GÉNÉRALE SUR MOCHA — MADAGASCAR** 🚨\n🎯 **Objectif :** *\"{texte_urgence}\"*\n⏱️ **Délai accordé :** `{delai_texte}`.\n👉 Tapez `!rejoindre_urgence` pour participer !")
        return

    if content_lower == "!rejoindre_urgence":
        if not urgence_active:
            await message.channel.send("❌ Aucune urgence active.")
            return
        if urgence_active.get("en_attente", False):
            await message.channel.send("❌ L'urgence est fermée, elle est en cours de validation par un Instructeur.")
            return
        if message.author.id in urgence_active["membres"]: return
        if message.author.id in missions_actives:
            await message.channel.send("❌ Tu as déjà une mission standard active.")
            return
        urgence_active["membres"].append(message.author.id)
        await message.channel.send(f"✅ {message.author.mention} a rejoint le front d'urgence pour Madagascar !")
        return

    # --- DECLARATION FIN ---
    if content_lower == "!fin":
        joueur = message.author
        role_instructeur = discord.utils.get(message.guild.roles, name="Instructeur")
        mention_ins = role_instructeur.mention if role_instructeur else '@Instructeur'
        
        if urgence_active and joueur.id in urgence_active["membres"]:
            if not urgence_active.get("en_attente", False):
                urgence_active["en_attente"] = True
                urgence_active["moment_gel"] = datetime.now()
            await message.channel.send(f"📢 {mention_ins} ! {joueur.mention} déclare avoir terminé l'URGENCE : *\"{urgence_active['texte']}\"* !\n⏱️ **Le chrono est mis en pause le temps des vérifications.**")
            return
            
        if joueur.id in missions_actives:
            m_info = missions_actives[joueur.id]
            if not m_info.get("en_attente", False):
                m_info["en_attente"] = True
                m_info["moment_gel"] = datetime.now()
            txt_cible = "L'escouade " + ", ".join([f"<@{uid}>" for uid in m_info["membres"]]) if len(m_info["membres"]) > 1 else joueur.mention
            await message.channel.send(f"📢 {mention_ins} ! {txt_cible} déclare avoir fini la mission : *\"{m_info['texte']}\"* !\n⏱️ **Le chrono est mis en pause le temps des vérifications.**")
            return
            
        await message.channel.send("❌ Tu n'as aucune mission ou urgence en cours.")
        return

    # --- VALIDATION FIN ET ÉCHEC CODES ---
    if content_lower.startswith("!missionfinit"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        
        if urgence_active and cible.id in urgence_active["membres"]:
            profils = charger_profils()
            for uid in urgence_active["membres"]:
                initialiser_profil(uid, profils)
                profils[str(uid)]["reussies"]["urgence"] += 1
                ajouter_historique(uid, profils, f"[URGENCE] {urgence_active['texte']}", "Succès")
            sauvegarder_profils(profils)
            st_g = charger_stats_globales()
            st_g["urgences_reussies"] += 1
            sauvegarder_stats_globales(st_g)
            await message.channel.send(f"👑 **URGENCE VALIDÉE AVEC SUCCÈS !** Félicitations à toute l'équipe de Madagascar.")
            urgence_active = {}
            return
            
        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            profils = charger_profils()
            for uid in m_info["membres"]:
                initialiser_profil(uid, profils)
                profils[str(uid)]["reussies"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Succès")
            sauvegarder_profils(profils)
            for uid in m_info["membres"]:
                if uid in missions_actives: del missions_actives[uid]
            await message.channel.send(f"✅ Mission validée avec succès par le Haut Commandement !")
            return
        await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    if content_lower.startswith("!missionechec"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        
        if urgence_active and cible.id in urgence_active["membres"]:
            if urgence_active.get("en_attente", False):
                urgence_active["en_attente"] = False
                temps_perdu_en_pause = datetime.now() - urgence_active["moment_gel"]
                urgence_active["date_fin"] += temps_perdu_en_pause
                await message.channel.send(f"❌ **Validation refusée.** L'objectif de l'urgence n'est pas rempli. Le chrono reprend !")
            else:
                if cible.id in urgence_active["membres"]: urgence_active["membres"].remove(cible.id)
                profils = charger_profils()
                initialiser_profil(cible.id, profils)
                profils[str(cible.id)]["echouees"]["urgence"] += 1
                ajouter_historique(cible.id, profils, f"[URGENCE] {urgence_active['texte']}", "Échec")
                sauvegarder_profils(profils)
                await message.channel.send(f"🚨 {cible.mention} a été sorti de l'urgence pour faute lourde.")
            return

        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            profils = charger_profils()
            escouade_membres = m_info["membres"]
            for uid in escouade_membres:
                initialiser_profil(uid, profils)
                profils[str(uid)]["echouees"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            for uid in escouade_membres:
                if uid in missions_actives: del missions_actives[uid]
                
            mentions = ", ".join([f"<@{uid}>" for uid in escouade_membres])
            await message.channel.send(
                f"↩️ **Mission invalidée par l'Instructeur.** L'objectif n'étant pas rempli, la quête retourne dans le panier.\n"
                f"📉 **Malus appliqué :** Un échec a été enregistré dans le profil de : {mentions}.\n\n{TEXTE_ECHEC}"
            )
            return
            
        await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    # --- COMMANDES DE MISSIONS CITOYENS ---
    if content_lower.startswith("!mission_groupe"):
        if urgence_active:
            await message.channel.send("🚨 **BLOCAGE** : Urgence nationale sur Mocha — Madagascar active !")
            return
        mots = content_lower.split()
        if len(mots) < 3: return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else: return

        escouade = [message.author.id]
        for m in message.mentions:
            if m.id not in escouade and not m.bot: escouade.append(m.id)
        if len(escouade) < 2:
            await message.channel.send("❌ Mentionne au moins un collègue.")
            return

        for uid in escouade:
            if uid in missions_actives:
                await message.channel.send("❌ Un membre du groupe est déjà occupé.")
                return

        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await message.channel.send("❌ Aucune mission disponible dans cette catégorie.")
            return
        mission_choisie = missions_dispo[cat].pop(random.randint(0, len(missions_dispo[cat]) - 1))
        réécrire_toutes_missions(missions_dispo)

        duree = extraire_duree(mission_choisie["delai"])
        m_data = {
            "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
            "date_debut": datetime.now(), "date_fin": datetime.now() + duree, "duree_totale": duree,
            "cat": cat, "channel_id": message.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "membres": escouade, "en_attente": False
        }
        for uid in escouade: missions_actives[uid] = m_data
        await message.channel.send(f"👥 **Mission de groupe lancée !** *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

    if content_lower.startswith("!mission"):
        if urgence_active:
            await message.channel.send("🚨 **BLOCAGE** : Urgence nationale sur Mocha — Madagascar active !")
            return
        joueur = message.author
        mots = content_lower.split()
        if len(mots) < 2: return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else: return

        if joueur.id in missions_actives:
            await message.channel.send("❌ Tu as déjà une mission en cours !")
            return

        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await message.channel.send("❌ Plus de mission dispo dans cette catégorie.")
            return
        mission_choisie = missions_dispo[cat].pop(random.randint(0, len(missions_dispo[cat]) - 1))
        réécrire_toutes_missions(missions_dispo)

        duree = extraire_duree(mission_choisie["delai"])
        missions_actives[joueur.id] = {
            "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
            "date_debut": datetime.now(), "date_fin": datetime.now() + duree, "duree_totale": duree,
            "cat": cat, "channel_id": message.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "membres": [joueur.id], "en_attente": False
        }
        await message.channel.send(f"📜 **Mission attribuée :** *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

    # --- STATS GLOBALES MADAGASCAR ---
    if content_lower == "!stats_royaume":
        profils = charger_profils()
        st_g = charger_stats_globales()
        t_reus, t_eche, max_act, top_user = 0, 0, 0, "Aucun"
        for u_id, st in profils.items():
            u_r = sum(st["reussies"].values())
            u_e = sum(st["echouees"].values())
            t_reus += u_r
            t_eche += u_e
            if (u_r + u_e) > max_act:
                max_act = (u_r + u_e)
                top_user = f"<@{u_id}>"
        t_tot = t_reus + t_eche
        t_tx = int((t_reus / t_tot) * 100) if t_tot > 0 else 100
        
        embed = discord.Embed(title="⚜️ ARCHIVES DE MADAGASCAR — STATISTIQUES ⚜️", color=discord.Color.dark_gold())
        embed.add_field(name="🌍 Total Décrets Tentés", value=f"`{t_tot}` missions", inline=True)
        embed.add_field(name="📈 Efficacité Citoyenne", value=f"`{t_tx}%` de réussite", inline=True)
        embed.add_field(name="🚨 Crises d'Urgence", value=f"✅ Réc: `{st_g['urgences_reussies']}` | ❌ Éch: `{st_g['urgences_echouees']}`", inline=False)
        embed.add_field(name="🏆 Citoyen le plus Actif", value=f"{top_user} avec `{max_act}` décrets", inline=False)
        await message.channel.send(embed=embed)
        return

    # --- FILES MANAGEMENT ADMIN COMMANDS ---
    if content_lower.startswith("!listemissions") and message.author.guild_permissions.administrator:
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **ARCHIVES DES MISSIONS DISPONIBLES** ⚜️\n"
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"\n__**{cat.upper()} :**__\n"
            if not missions_dispo[cat]: reponse += "*Aucune mission disponible*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1): reponse += f"**{i}.** {m['texte']} *(Délai d'origine : {m['delai']})*\n"
        await message.channel.send(reponse[:2000])
        return

    if content_lower.startswith("!addmission") and message.author.guild_permissions.administrator:
        texte_total = content[11:].strip()
        mots = texte_total.split()
        if len(mots) < 4 or "pendant" not in texte_total.lower():
            await message.channel.send("❌ Format incorrect. Exemple : `!addmission commune Miner 50 diamants pendant 2h`")
            return
        cat = mots[0].lower()
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Catégorie inconnue (`commune`, `moyenne`, `difficile`, `royal`).")
            return
        parties = texte_total.split(None, 1)[1].strip()
        index_pendant = parties.lower().rfind("pendant")
        texte_mission = parties[:index_pendant].strip()
        delai = parties[index_pendant + 7:].strip()
        sauvegarder_mission_fichier(cat, texte_mission, delai)
        missions_dispo = charger_missions_fichier()
        await message.channel.send(f"⚜️ **Mission ajoutée au catalogue !** (`{cat}` : *{texte_mission}*)")
        return

    if content_lower.startswith("!delmission") and message.author.guild_permissions.administrator:
        mots = content_lower.split()
        if len(mots) < 3: return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        try: numero = int(mots[2]) - 1
        except ValueError: return
        missions_dispo = charger_missions_fichier()
        if cat in missions_dispo and 0 <= numero < len(missions_dispo[cat]):
            retiree = missions_dispo[cat].pop(numero)
            réécrire_toutes_missions(missions_dispo)
            await message.channel.send(f"🗑️ Mission *\"{retiree['texte']}\"* supprimée avec succès.")
        else:
            await message.channel.send("❌ Numéro invalide ou mission introuvable.")
        return

    # --- CONSULTATION PROFIL ---
    if content_lower.startswith("!profil"):
        cible = message.mentions[0] if message.mentions else message.author
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        
        stats = profils[str(cible.id)]
        rang = calculer_rang(stats)
        
        reussies_totales = sum(stats["reussies"].values())
        echouees_totales = sum(stats["echouees"].values())
        total_missions = reussies_totales + echouees_totales
        taux_reussite = int((reussies_totales / total_missions) * 100) if total_missions > 0 else 100
        
        embed = discord.Embed(title=f"⚜️ PROFIL CITOYEN — {cible.display_name} ⚜️", color=discord.Color.blue())
        embed.set_thumbnail(url=cible.display_avatar.url)
        embed.add_field(name="🎖️ Rang Militaire", value=f"**{rang}**", inline=False)
        
        missions_txt = (
            f"🟢 **Réussies :** {reussies_totales}\n"
            f"↳ *Communes: {stats['reussies']['commune']} | Moyennes: {stats['reussies']['moyenne']} | Difficiles: {stats['reussies']['difficile']} | Royales: {stats['reussies']['royal']} | Urgences: {stats['reussies']['urgence']}*\n\n"
            f"🔴 **Échouées :** {echouees_totales}\n"
            f"↳ *Communes: {stats['echouees']['commune']} | Moyennes: {stats['echouees']['moyenne']} | Difficiles: {stats['echouees']['difficile']} | Royales: {stats['echouees']['royal']} | Urgences: {stats['echouees']['urgence']}*"
        )
        embed.add_field(name="⚔️ Statistiques des Décrets", value=missions_txt, inline=False)
        embed.add_field(name="📈 Taux d'Efficacité", value=f"`{taux_reussite}%` de réussite globale", inline=True)
        
        await message.channel.send(embed=embed)
        return

    # --- HISTORIQUE DES ACTIONS ---
    if content_lower == "!historique":
        joueur = message.author
        profils = charger_profils()
        initialiser_profil(joueur.id, profils)
        hist = profils[str(joueur.id)]["historique"]
        
        embed = discord.Embed(title=f"📜 PARCHEMIN D'ARMES — {joueur.display_name}", color=discord.Color.light_grey())
        if not hist:
            embed.description = "*Aucune action enregistrée dans les archives.*"
        else:
            for item in hist:
                statut_emoji = "✅" if item["statut"] == "Succès" else "❌" if item["statut"] == "Échec" else "⚙️"
                embed.add_field(name=f"{statut_emoji} [{item['date']}] - {item['statut']}", value=f"*{item['texte']}*", inline=False)
        await message.channel.send(embed=embed)
        return

# Lancement du serveur Web et du Bot
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Erreur : Aucun token Discord trouvé dans les variables d'environnement.")
