import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
import json
import asyncio
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

def initialiser_profil(p_id, profils):
    s_id = str(p_id)
    if s_id not in profils:
        profils[s_id] = {
            "total_reussies": 0,
            "total_echouees": 0,
            "historique": []
        }

def ajouter_historique(p_id, profils, texte, statut):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    profils[s_id]["historique"].insert(0, {
        "texte": texte,
        "statut": statut,
        "date": datetime.now().strftime("%d/%m/%Y à %H:%M")
    })

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

TEXTE_ECHEC = (
    "⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖊 𝕸𝖆𝖉𝖆𝖈𝖆𝖘𝖈𝖆𝖗** ⚜️\n"
    "**D'après l'article Ⅴ — Rappel :**\n"
    "- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
    "- *L'État récompense l'investissement et la persévérance.*\n"
    "- *Les missions constituent l'un des principaux moyens de progresser au sein de Madagascar.*"
)

def verifier_permissions_staff(user):
    roles_noms = [r.name for r in user.roles]
    return user.guild_permissions.administrator or "[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]" in roles_noms or "Palais Royal" in roles_noms

async def envoyer_double_notification(guild, msg_ticket, msg_missions, view=None):
    salon_missions = discord.utils.get(guild.text_channels, name="validation-mission")
    if salon_missions and msg_missions:
        try: await salon_missions.send(msg_missions, view=view)
        except: pass

class VueFermerTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def fermer_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Suppression du salon en cours...", ephemeral=True)
        try: await interaction.channel.delete()
        except: pass

async def action_accepter_mission(joueur_id, channel):
    if joueur_id in missions_actives:
        m_info = missions_actives[joueur_id]
        profils = charger_profils()
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_reussies"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Succès")
        sauvegarder_profils(profils)
        del missions_actives[joueur_id]
        
        msg = "✅ **Mission Validée** ! L'objectif est consigné comme réussi dans le grand registre."
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(channel.guild, msg, f"✅ **Mission accomplie** par <@{joueur_id}> : *\"{m_info['texte']}\"*")
        return True
    return False

async def action_refuser_mission(joueur_id, channel):
    if joueur_id in missions_actives:
        m_info = missions_actives[joueur_id]
        profils = charger_profils()
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_echouees"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
        sauvegarder_profils(profils)
        del missions_actives[joueur_id]
        
        msg = f"↩️ **Mission Terminée (Refusé/Échec)**.\n\n{TEXTE_ECHEC}"
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(channel.guild, msg, f"❌ **Mission échouée/refusée** pour <@{joueur_id}> : *\"{m_info['texte']}\"*")
        return True
    return False

async def action_demander_preuve(joueur_id, channel, guild):
    if joueur_id in missions_actives:
        m_info = missions_actives[joueur_id]
        m_info["en_attente"] = True # Gèle le chrono
        
        member = guild.get_member(joueur_id)
        if member:
            # Redonne l'accès d'écriture au joueur pour envoyer sa capture d'écran
            await channel.set_permissions(member, read_messages=True, send_messages=True)
            
        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]"
        
        msg_ticket = f"⚠️ <@{joueur_id}>, **{mention_ins} vous demande de fournir une preuve (capture d'écran) de l'accomplissement de votre mission dans ce salon.**"
        await channel.send(msg_ticket)
        
        # Envoie un NOUVEAU message dans validation-mission avec la vue sans le bouton preuve
        msg_log_missions = f"📸 {mention_ins} — Demande de preuve envoyée à <@{joueur_id}> pour son ticket {channel.mention}.\n*Veuillez valider ou refuser une fois la preuve vérifiée :*"
        await envoyer_double_notification(guild, "", msg_log_missions, view=VueEvaluationApresPreuve(joueur_id))
        return True
    return False

async def gerer_expiration_automatique(guild, channel_id, joueur_id):
    await asyncio.sleep(3600)
    
    if joueur_id not in missions_actives:
        channel = bot.get_channel(channel_id)
        if not channel: return
        
        expiration_time = int((datetime.now() + timedelta(hours=1)).timestamp())
        member = guild.get_member(joueur_id)
        mention_joueur = member.mention if member else f"<@{joueur_id}>"
        
        msg_expiration_auto = (
            f"⚠️ {mention_joueur}, **attention : aucune mission n'a été sélectionnée depuis 1 heure.**\n"
            f"Cet ordre de mission sera définitivement supprimé et annulé **<t:{expiration_time}:R>** (<t:{expiration_time}:t>)."
        )
        try: await channel.send(msg_expiration_auto)
        except: return

        await asyncio.sleep(3600)
        
        if joueur_id not in missions_actives:
            channel_final = bot.get_channel(channel_id)
            if channel_final:
                try:
                    await channel_final.delete(reason="Expiration de l'ordre de mission (2 heures d'inactivité au total)")
                    await envoyer_double_notification(guild, "", f"🗑️ Le ticket d'ordre de {mention_joueur} a été supprimé automatiquement pour inactivité (1h attente + 1h avertissement).")
                except Exception as e:
                    print(f"Erreur lors de la suppression : {e}")

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    maintenant = datetime.now()
    missions_a_retirer = []
    
    for joueur_id, m_info in list(missions_actives.items()):
        if m_info.get("en_attente", False): continue
        
        channel = bot.get_channel(m_info["channel_id"])
        if not channel: continue
        
        duree_totale = m_info["duree_totale"]
        date_debut = m_info["date_debut"]
        date_fin = m_info["date_fin"]
        temps_restant = date_fin - maintenant
        temps_ecoule = maintenant - date_debut

        if maintenant > date_fin:
            missions_a_retirer.append(joueur_id)
            profils = charger_profils()
            initialiser_profil(joueur_id, profils)
            profils[str(joueur_id)]["total_echouees"] += 1
            ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            role_instructeur = discord.utils.get(channel.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
            mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]'
            
            msg_echec = (
                f"🚨 **MISSION ÉCHOUÉE** 🚨\nLe temps imparti est écoulé ! La mission de <@{joueur_id}> a échoué.\n"
                f"📢 {mention_ins}, un citoyen a failli à son devoir.\n\n{TEXTE_ECHEC}"
            )
            await channel.send(msg_echec, view=VueFermerTicket())
            await envoyer_double_notification(channel.guild, msg_echec, f"🚨 <@{joueur_id}> a dépassé le temps imparti pour sa mission : *\"{m_info['texte']}\"* !")
            
        elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
            m_info["alerte_un_quart"] = True
            m_info["alerte_moitie"] = True
            jours = temps_restant.days
            heures, reste = divmod(temps_restant.seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            await channel.send(f"⏳ **CRITIQUE** <@{joueur_id}> : -25% du temps restant ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
        elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
            m_info["alerte_moitie"] = True
            await channel.send(f"🌗 **MI-PARCOURS** <@{joueur_id}> : la moitié du temps s'est écoulée !")

    for joueur_id in missions_a_retirer:
        if joueur_id in missions_actives: del missions_actives[joueur_id]

class VueBoutonTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un Ticket de Mission", style=discord.ButtonStyle.green, custom_id="btn_ouvrir_ticket")
    async def ouvrir_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        joueur = interaction.user
        
        nom_categorie_requis = "⚜️ == [ 𝕸𝖎𝖘𝖘𝖎𝖔𝖓 ] == ⚜️"
        cat_cible = discord.utils.get(guild.categories, name=nom_categorie_requis)
        if not cat_cible:
            cat_cible = await guild.create_category(nom_categorie_requis)

        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            joueur: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if role_instructeur:
            overwrites[role_instructeur] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        nom_salon = f"ordre-de-{joueur.name.lower().replace(' ', '-')}"
        salon_ticket = await guild.create_text_channel(nom_salon, category=cat_cible, overwrites=overwrites)
        
        await interaction.response.send_message(f"✅ Votre ticket de mission a été créé : {salon_ticket.mention}", ephemeral=True)
        
        view = VueChoixMissions(joueur.id)
        embed = discord.embeds.Embed(
            title="📜 Demande d'Ordre de Mission",
            description=f"Bienvenue {joueur.mention}.\nChoisissez le type de mission que vous souhaitez accomplir ci-dessous :",
            color=discord.Color.gold()
        )
        await salon_ticket.send(embed=embed, view=view)
        bot.loop.create_task(gerer_expiration_automatique(guild, salon_ticket.id, joueur.id))

class VueChoixMissions(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    async def piocher_et_affecter(self, interaction: discord.Interaction, categorie_nom, nom_lisible):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Ce salon de choix est réservé à la personne qui l'a ouvert !", ephemeral=True)
            return

        liste = missions_dispo.get(categorie_nom, [])
        if not liste:
            await interaction.response.send_message(f"❌ Aucune mission de catégorie **{nom_lisible}** n'est enregistrée.", ephemeral=True)
            return

        mission = random.choice(liste)
        delai_texte = mission['delai']
        delta_temps = extraire_duree(delai_texte)
        date_debut = datetime.now()
        date_fin = date_debut + delta_temps
        
        missions_actives[self.joueur_id] = {
            "texte": mission['texte'],
            "delai_texte": delai_texte,
            "duree_totale": delta_temps,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "channel_id": interaction.channel_id,
            "alerte_moitie": False,
            "alerte_un_quart": False,
            "en_attente": False
        }

        role_instructeur = discord.utils.get(interaction.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]"
        timestamp_fin = int(date_fin.timestamp())

        embed = discord.Embed(
            title=f"📜 Ordre de Mission attribué — {nom_lisible}",
            description=(
                f"👤 **Attribué à :** {interaction.user.mention}\n"
                f"🎯 **Mission :** {mission['texte']}\n"
                f"⏳ **Délai :** {delai_texte}\n"
                f"⏰ **Heure limite :** <t:{timestamp_fin}:F> (<t:{timestamp_fin}:R>)"
            ),
            color=discord.Color.blue()
        )
        
        view_eval = VueEvaluationMission(self.joueur_id)
        
        await interaction.response.defer()
        await interaction.message.delete()
        await interaction.channel.send(embed=embed)
        
        msg_instructeur = f"🔔 **{mention_ins}**, un nouveau citoyen a tiré une mission ({nom_lisible})."
        await interaction.channel.send(msg_instructeur)
        
        msg_validation = (
            f"📥 **Nouvelle mission en cours !**\n"
            f"• **Joueur :** {interaction.user.mention}\n"
            f"• **Rareté :** {nom_lisible}\n"
            f"• **Intitulé :** {mission['texte']}\n"
            f"• **Fin prévue :** <t:{timestamp_fin}:F> (<t:{timestamp_fin}:R>)\n"
            f"• **Ticket :** {interaction.channel.mention}"
        )
        await envoyer_double_notification(interaction.guild, "", msg_validation, view=view_eval)

    @discord.ui.button(label="🟢 Commune", style=discord.ButtonStyle.secondary, custom_id="btn_commune")
    async def btn_commune(self, i, b): await self.piocher_et_affecter(i, "commune", "Commune 🟢")

    @discord.ui.button(label="🔵 Moyenne", style=discord.ButtonStyle.primary, custom_id="btn_moyenne")
    async def btn_moyenne(self, i, b): await self.piocher_et_affecter(i, "moyenne", "Moyenne 🔵")

    @discord.ui.button(label="🔴 Difficile", style=discord.ButtonStyle.danger, custom_id="btn_difficile")
    async def btn_difficile(self, i, b): await self.piocher_et_affecter(i, "difficile", "Difficile 🔴")

    @discord.ui.button(label="👑 Royal", style=discord.ButtonStyle.success, custom_id="btn_royal")
    async def btn_royal(self, i, b): await self.piocher_et_affecter(i, "royal", "Royal 👑")


# --- VUE STANDARD DE VALIDATION (AVEC BOUTON DE DEMANDE DE PREUVE) ---
class VueEvaluationMission(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="btn_accepter_m")
    async def accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Vous devez être Instructeur ou Administrateur.", ephemeral=True)
            return
        
        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Mission introuvable ou déjà terminée.", ephemeral=True)
            return

        channel = bot.get_channel(missions_actives[self.joueur_id]["channel_id"])
        if channel:
            res = await action_accepter_mission(self.joueur_id, channel)
            if res:
                button.disabled = True
                self.stop()
                await interaction.response.edit_message(content=f"{interaction.message.content}\n\n✅ **Mission ACCEPTEE par {interaction.user.mention}**", view=None)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="btn_refuser_m")
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Vous devez être Instructeur ou Administrateur.", ephemeral=True)
            return
        
        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Mission introuvable ou déjà terminée.", ephemeral=True)
            return

        channel = bot.get_channel(missions_actives[self.joueur_id]["channel_id"])
        if channel:
            res = await action_refuser_mission(self.joueur_id, channel)
            if res:
                self.stop()
                await interaction.response.edit_message(content=f"{interaction.message.content}\n\n❌ **Mission REFUSÉE par {interaction.user.mention}**", view=None)

    @discord.ui.button(label="📸 Demander des preuves", style=discord.ButtonStyle.primary, custom_id="btn_preuve_m")
    async def preuve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Vous devez être Instructeur ou Administrateur.", ephemeral=True)
            return
        
        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Mission introuvable ou déjà terminée.", ephemeral=True)
            return

        channel = bot.get_channel(missions_actives[self.joueur_id]["channel_id"])
        if channel:
            res = await action_demander_preuve(self.joueur_id, channel, interaction.guild)
            if res:
                self.stop()
                await interaction.response.edit_message(content=f"{interaction.message.content}\n\n📸 **Demande de preuve envoyée par {interaction.user.mention}**", view=None)


# --- NOUVELLE VUE : UTILISÉE APRÈS UNE DEMANDE DE PREUVE (PAS DE BOUTON PREUVE DEDANS) ---
class VueEvaluationApresPreuve(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter la mission", style=discord.ButtonStyle.success, custom_id="btn_accepter_m_post")
    async def accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Vous devez être Instructeur ou Administrateur.", ephemeral=True)
            return
        
        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Mission introuvable ou déjà terminée.", ephemeral=True)
            return

        channel = bot.get_channel(missions_actives[self.joueur_id]["channel_id"])
        if channel:
            res = await action_accepter_mission(self.joueur_id, channel)
            if res:
                self.stop()
                await interaction.response.edit_message(content=f"{interaction.message.content}\n\n✅ **Mission ACCEPTEE suite aux preuves par {interaction.user.mention}**", view=None)

    @discord.ui.button(label="❌ Refuser la mission", style=discord.ButtonStyle.danger, custom_id="btn_refuser_m_post")
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Vous devez être Instructeur ou Administrateur.", ephemeral=True)
            return
        
        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Mission introuvable ou déjà terminée.", ephemeral=True)
            return

        channel = bot.get_channel(missions_actives[self.joueur_id]["channel_id"])
        if channel:
            res = await action_refuser_mission(self.joueur_id, channel)
            if res:
                self.stop()
                await interaction.response.edit_message(content=f"{interaction.message.content}\n\n❌ **Mission REFUSÉE suite aux preuves par {interaction.user.mention}**", view=None)


@bot.event
async def on_message(message):
    if message.author.bot: return

    # Si un joueur envoie un fichier/image dans son ticket alors qu'une preuve était demandée
    if message.author.id in missions_actives:
        m_info = missions_actives[message.author.id]
        if m_info.get("en_attente", False) and message.channel.id == m_info["channel_id"]:
            if message.attachments:
                role_instructeur = discord.utils.get(message.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
                mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]"
                
                await message.channel.send(f"📸 **Preuve déposée par {message.author.mention} !**\n{mention_ins}, une preuve a été postée. Merci de valider ou refuser la mission.")
                
                # Envoie un nouveau panneau avec les boutons d'acceptation/refus
                msg_validation = (
                    f"📸 **Nouvelle preuve soumise par {message.author.mention} !**\n"
                    f"• **Ticket :** {message.channel.mention}\n"
                    f"• **Lien de l'image :** {message.attachments[0].url}"
                )
                await envoyer_double_notification(message.guild, "", msg_validation, view=VueEvaluationApresPreuve(message.author.id))

    await bot.process_commands(message)

# --- COMMANDES D'ADMINISTRATION & PROFIL ---

@bot.tree.command(name="creer_panel", description="Crée le panneau permanent pour ouvrir les tickets de missions")
async def creer_panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Vous n'avez pas la permission.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖊 𝕸𝖆𝖉𝖆𝖈𝖆𝖘𝖈𝖆𝖗** ⚜️",
        description=(
            "**D'après l'article Ⅴ :**\n"
            "- *Tout citoyen peut demander un ordre de mission auprès des instructeurs.*\n"
            "- *L'État récompense l'investissement et la persévérance.*\n\n"
            "Cliquez sur le bouton ci-dessous pour ouvrir un ticket et recevoir votre ordre de mission."
        ),
        color=discord.Color.gold()
    )
    await interaction.channel.send(embed=embed, view=VueBoutonTicket())
    await interaction.response.send_message("✅ Panneau créé avec succès !", ephemeral=True)

@bot.tree.command(name="add_mission", description="Ajouter une mission")
async def add_mission(interaction: discord.Interaction, categorie: str, texte: str, delai: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Seul un Instructeur ou Admin peut faire ça.", ephemeral=True)
        return
    cat = categorie.lower().strip()
    if cat not in missions_dispo:
        await interaction.response.send_message("❌ Catégories valides : `commune`, `moyenne`, `difficile`, `royal`", ephemeral=True)
        return
    
    missions_dispo[cat].append({"texte": texte, "delai": delai})
    sauvegarder_mission_fichier(cat, texte, delai)
    await interaction.response.send_message(f"✅ Mission ajoutée dans **{cat}** :\n📜 *{texte}* (⏳ {delai})")

@bot.tree.command(name="del_mission", description="Supprimer une mission grâce à son texte")
async def del_mission(interaction: discord.Interaction, categorie: str, texte_exact: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Seul un Instructeur ou Admin peut faire ça.", ephemeral=True)
        return
    cat = categorie.lower().strip()
    if cat not in missions_dispo:
        await interaction.response.send_message("❌ Catégories valides : `commune`, `moyenne`, `difficile`, `royal`", ephemeral=True)
        return
    
    anciennes = missions_dispo[cat]
    nouvelles = [m for m in anciennes if m['texte'] != texte_exact]
    if len(anciennes) == len(nouvelles):
        await interaction.response.send_message(f"❌ Aucune mission trouvée avec ce texte exact.", ephemeral=True)
        return
    
    missions_dispo[cat] = nouvelles
    réécrire_toutes_missions(missions_dispo)
    await interaction.response.send_message(f"🗑️ Mission supprimée de la catégorie **{cat}**.")

@bot.tree.command(name="profil", description="Voir les statistiques et l'historique d'un membre")
async def profil(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    profils = charger_profils()
    s_id = str(target.id)
    
    if s_id not in profils:
        await interaction.response.send_message(f"📜 Aucun historique de mission trouvé pour {target.mention}.", ephemeral=True)
        return
    
    data = profils[s_id]
    reussies = data.get("total_reussies", 0)
    echouees = data.get("total_echouees", 0)
    total = reussies + echouees
    taux = round((reussies / total) * 100, 1) if total > 0 else 0
    
    embed = discord.Embed(
        title=f"📜 Profil de Mission — {target.display_name}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="✅ Réussies", value=str(reussies), inline=True)
    embed.add_field(name="❌ Échouées", value=str(echouees), inline=True)
    embed.add_field(name="📊 Taux de succès", value=f"{taux}%", inline=True)
    
    histo_text = ""
    for h in data.get("historique", [])[:5]:
        ic = "✅" if h["statut"] == "Succès" else "❌"
        histo_text += f"{ic} **{h['texte']}**\n┗ 📅 *{h['date']}*\n"
    
    if histo_text: embed.add_field(name="📜 Dernières missions", value=histo_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    # Enregistrement universel des vues pour éviter le dysfonctionnement au redémarrage du bot
    bot.add_view(VueBoutonTicket())
    bot.add_view(VueEvaluationMission(None))
    bot.add_view(VueEvaluationApresPreuve(None))
    
    if not verifier_temps_missions.is_running():
        verifier_temps_missions.start()
        
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commande(s) Slash synchronisée(s).")
    except Exception as e:
        print(f"❌ Erreur lors du sync : {e}")
        
    print(f"🤖 Bot connecté en tant que {bot.user}")

keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
