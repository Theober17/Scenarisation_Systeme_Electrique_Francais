import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import itertools

def ajuster_flexibilite(conso_horaire, flex_gwh=15):
    # Conversion de la flexibilité en MWh
    flex_mwh = flex_gwh * 1000
    
    # Nombre d'heures dans une journée
    heures_par_jour = 24
    
    # La nouvelle liste modifiée
    conso_modifiee = conso_horaire.copy()
    
    # Parcourir les jours de l'année
    for jour in range(len(conso_horaire) // heures_par_jour):
        # Déterminer les indices des heures du jour actuel
        debut = jour * heures_par_jour
        fin = debut + heures_par_jour
        
        # Vérifier que la tranche contient bien 24 heures
        journee = conso_modifiee[debut:fin]
        
        # Trier les indices par consommation décroissante (pour heures critiques)
        heures_critiques = sorted(range(heures_par_jour), key=lambda i: journee[i], reverse=True)[:7]
        
        # Trier les indices par consommation croissante (pour heures creuses)
        heures_creuses = sorted(range(heures_par_jour), key=lambda i: journee[i])[:7]
        
        # Réduction par heure critique et augmentation par heure creuse
        reduction_par_heure = flex_mwh / len(heures_critiques)
        augmentation_par_heure = flex_mwh / len(heures_creuses)
        
        for h in heures_critiques:
            journee[h] -= reduction_par_heure
        
        for h in heures_creuses:
            journee[h] += augmentation_par_heure
        
        # Mettre à jour les consommations dans la liste modifiée
        conso_modifiee[debut:fin] = journee
    
    return conso_modifiee

def simulateur_systeme_electrique_francais(scenario_prod, scenario_cons, ramp_nucbase, FC_min_nucbase, ramp_coal, FC_min_coal, ramp_gasCC, FC_min_gasCC, ramp_nucflex, FC_min_nucflex, ramp_fuel, FC_min_fuel, ramp_import, ramp_export):

    #Consommation en fonction du scénario
    scenarios_conso = {"réindustrialisation" : 752,
                  "sobriété" : 555,
                  "efficassité électrique moindre" : 714,
                  "électrification +" : 700,
                  "électrification -" : 578,
                  "Hydrogène +" : 754}
    
    #Pourcentage de perte (pertes en lignes etc.)
    perte = 7 / 100

    prix_tonne_CO2 = 100

    #Ordre d'effacement es EnR
    ordre = 2 

    #Données scénario
    df_scenario = pd.read_csv('data_new\scenarios_RTE_Prod.csv', sep=';', header=0)
    df_historique = pd.read_csv('data\data_historique.csv', sep=';', header=0)
    df_bdd_systeme = pd.read_csv(r'data\bdd_systeme.csv', sep=';', header=0, nrows=8760, usecols=range(8))
    df_bdd_ventoff = pd.read_csv(r'data\bdd_ventoff.csv', sep=';', header=0)

    # Filtrer le DataFrame selon les conditions
    df_scenario = df_scenario[df_scenario['scénario'] == scenario_prod]
    df_historique = df_historique[df_historique['Annee'] == 2018]

    #Ajustement des facteurs de capacités du scénario
    FChydro = float(df_scenario["FC (%)"][df_scenario["Filière"] == "hydraulique"].iloc[0])
    FCwindon = float(df_scenario["FC (%)"][df_scenario["Filière"] == "éolien onshore"].iloc[0])
    FCPV = float(df_scenario["FC (%)"][df_scenario["Filière"] == "photovoltaïque"].iloc[0])

    FChydrob = float(df_historique["FC(%)"][df_historique["Source"] == "hydraulique"].iloc[0])
    FCwindonb = float(df_historique["FC(%)"][df_historique["Source"] == "eolien on"].iloc[0])
    FCPVb = float(df_historique["FC(%)"][df_historique["Source"] == "photovoltaique"].iloc[0])

    ec_FChydro = (FChydro - FChydrob) / FChydrob
    ec_FCwindon = (FCwindon - FCwindonb) / FCwindonb
    ec_FCPV = (FCPV - FCPVb) / FCPVb

    Khydro = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "hydraulique"].iloc[0]) * 1000
    Kwindon = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "éolien onshore"].iloc[0]) * 1000
    KPV = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "photovoltaïque"].iloc[0]) * 1000
    Kbiomas = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "bioénergies"].iloc[0]) * 1000
    KwindoffT = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "éolien offshore"].iloc[0]) * 1000

    conso_annuelle = scenarios_conso[scenario_cons] * 1000000 #TWh en MWh
    conso_horaire = df_bdd_systeme['consommation'] * conso_annuelle
    conso_horaire_flex = ajuster_flexibilite(list(conso_horaire))

    hydro_horaire = df_bdd_systeme['hydraulique'] * (1 + ec_FChydro) * Khydro

    hydro_horaire[hydro_horaire > 0.8 * Khydro] = 0.8 * Khydro
    hydro_horaire[hydro_horaire < 0.065 * Khydro] = 0.065 * Khydro

    windon_horaire = df_bdd_systeme['éolien onshore'] * (1 + ec_FCwindon) * Kwindon

    windon_horaire[windon_horaire > 0.92 * Kwindon] = 0.92 * Kwindon
    windon_horaire[windon_horaire < 0.002 * Kwindon] = 0.002 * Kwindon

    PV_horaire = df_bdd_systeme['solaire'] * (1 + ec_FCPV) * KPV
    PV_horaire[PV_horaire > 0.98 * KPV] = 0.98 * KPV
    PV_horaire[PV_horaire < 0] = 0

    bioenergies_horaire = df_bdd_systeme['biomasse'] * Kbiomas

    nord_ouest = (df_bdd_ventoff['Somme'] + df_bdd_ventoff['Seine-Maritime'] + df_bdd_ventoff['Nord'] + df_bdd_ventoff['Calvados']) / 4
    ouest = (df_bdd_ventoff['Loire-Atlantique'] + df_bdd_ventoff['Cote d Armor']) / 2
    sud_ouest = (df_bdd_ventoff['Gironde'] + df_bdd_ventoff['Charante Maritime']) / 2
    sud = (df_bdd_ventoff['Herault'] + df_bdd_ventoff['Bouches-du-Rhone']) / 2


    windoff_horaire = ((nord_ouest + ouest + sud_ouest + sud) / 4) * KwindoffT

    nucbase_variation = [True] * 8770
    nucflex_variation = [True] * 8770

    fuel_variation = [True] * 9000
    gasCC_variation2 = [True] * 9000
    gasCC_variation = [True] * 9000
    nucbase_variation2 = [True] * 9000
    export_variation = [True] * 9000
    import_variation = [True] * 9000

    tech1 = [0] * 8760
    tech2 = [0] * 8760
    tech3 = [0] * 8760

    tech1_curtailment = [0] * 8760
    tech2_curtailment = [0] * 8760
    tech3_curtailment = [0] * 8760


    #Nucléaire pour la base
    Knucbase = round(float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "nucléaire base"].iloc[0]) * 1000 / (1 + perte), 1)
    min_nucbase = round((FC_min_nucbase / 100) * Knucbase, 1)
    max_nucbase = round(Knucbase * 0.9, 1)
    ramp_nucbase = ramp_nucbase / 100

    #Nucléaire pour la pointe
    Knucflex =  round(float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "nucléaire flexible"].iloc[0]) * 1000 / (1 + perte))
    min_nucflex = round((FC_min_nucflex / 100) * Knucflex, 1)
    max_nucflex = round(Knucflex * 0.7, 1)
    ramp_nucflex = ramp_nucflex / 100

    #Charbon 
    Kcoal = 0
    min_coal = (FC_min_coal / 100) * Kcoal
    max_coal = 0
    ramp_coal = ramp_coal / 100

    #Pétrole
    Kfuel = round(float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "pétrole"].iloc[0]) * 1000 / (1 + perte), 1)
    min_fuel = round((FC_min_fuel / 100) * Kfuel, 2)
    max_fuel = Kfuel
    ramp_fuel = ramp_fuel / 100

    #Gaz cycle combinés et exports 
    KgasCC = round(float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "gaz"].iloc[0]) * 1000 / (1 + perte), 1)
    min_gasCC = round((FC_min_gasCC / 100) * KgasCC, 1)
    max_gasCC = KgasCC
    ramp_gasCC = ramp_gasCC / 100

    Kexport = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "exports"].iloc[0]) * 1000
    Kimport = round(float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "imports"].iloc[0]) * 1000 / (1 + perte), 1)
    ramp_export = ramp_export / 100
    ramp_import = ramp_import / 100

    storagecharge_variation = True
    storagedecharge_variation = True

    storagecharge_variation_th = True
    storagedecharge_variation_th = True

    #Stockage STEP (Station de Transfert d'Énergie par Pompage)
    max_stock = 3.591 * 1000000 #Energie maximale stockée [MWh]
    stock = max_stock / 2

    max_discharge = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "STEP"].iloc[0]) * 1000 #Puissance maximale durant lâcher d'eau [MWh]
    max_charge = 0.8 * max_discharge #Puissance maximale consommée pour pomper m'eau [MWh]

    #Thermique décarbonné
    max_stock_th = 200 * 1000000
    stock_th = 0

    max_discharge_th = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "thermique décarboné"].iloc[0] + 1.7) * 1000 #Puissance maximale combustion d'hydrogène [MWh]
    max_charge_th = 0.8 * max_discharge #Puissance maximale pour créer de l'hydrogène [MWh]

    #Coût des combustibles [euros/MWh] coût marginal + tonne CO2
    coût_gaz = 84 
    coût_coal = 110
    coût_fuel = 130 


    Positionnemet_batteries = 1 #En dernière position dans l'ordre 

    previous_nucbase = max_nucbase
    previous_nucflex = max_nucflex * 0.7
    previous_coal = max_coal
    previous_fuel = max_fuel
    previous_gasCC = max_gasCC
    previous_export = Kexport * ramp_export
    previous_import = 0

    coal = [0] * 8760
    fuel = [0] * 8760
    gasCC = [0] * 8760

    nucflex = [0] * 8760
    nucbase = [0] * 8760

    import_ = [0] * 8760
    export = [0] * 8760

    effacement = [0] * 8760
    effacement1 = [0] * 8760
    effacement2 = [0] * 8760

    PV_curtailment = [0] * 8760
    windon_curtailment = [0] * 8760
    windoff_curtailment = [0] * 8760
    storage_charge = [0] * 8760
    storage_discharge = [0] * 8760
    storage_charge_th = [0] * 8760
    storage_discharge_th = [0] * 8760

    bat_charge = [0] * 8760
    bat_discharge = [0] * 8760
    cycles = [0] * 8760
    stocks = [0] * 8760

    variation_need_list = []

    #Parc de batteries
    maxbat = float(df_scenario["Parc installé (GW)"][df_scenario["Filière"] == "batteries"].iloc[0]) * 1000 #Capacité des batterie en MWh
    minbat = 0
    rampbat = 100 / 100
    bat_stock = minbat
    previous_bat = minbat

    windoffT = [0] * 8760
    pertes = [0] * 8760
    col39 = []

    v_excess = 0
    nb_excess = 0

    v_lack = 0
    nb_lack = 0

    if Positionnemet_batteries == 1 :

        for tranche_horaire in range(8760) :
        
            windoffT[tranche_horaire] = windoff_horaire[tranche_horaire]
            pertes[tranche_horaire] = (hydro_horaire[tranche_horaire] + windon_horaire[tranche_horaire] + PV_horaire[tranche_horaire] + bioenergies_horaire[tranche_horaire] + windoffT[tranche_horaire]) * perte

            if (tranche_horaire < 1415) or (tranche_horaire > 8016) : #Decembre à Mars
                max_nucbase = Knucbase * 0.91
                max_nucflex = Knucflex * 0.91
            else :
                if (tranche_horaire < 2879) : #Mars à Mai

                    max_nucbase = Knucbase * 0.8
                    max_nucflex = Knucflex * 0.8
                else :
                    if (tranche_horaire < 7295) : #Mai à Novembre
                        max_nucbase = Knucbase * 0.67
                        max_nucflex = Knucflex * 0.67

                    else : #Novembre à decembre
                        max_nucbase = Knucbase * 0.8
                        max_nucflex = Knucflex * 0.8
                
            if fuel_variation[tranche_horaire] == True :
                previous_fuel = previous_fuel
            else :
                if previous_fuel > min_fuel :
                    previous_fuel = previous_fuel * 0.1
                else :
                    previous_fuel = min_fuel

            if gasCC_variation2[tranche_horaire] == True :
                previous_gasCC = previous_gasCC
            else :
                if previous_gasCC > max_gasCC * 0.01 :
                    previous_gasCC = previous_gasCC * 0.6
                else :
                    previous_gasCC = max_gasCC * 0.01

            variation_need = (conso_horaire_flex[tranche_horaire] + pertes[tranche_horaire] - hydro_horaire.iloc[tranche_horaire] - PV_horaire.iloc[tranche_horaire] - windon_horaire.iloc[tranche_horaire] - windoffT[tranche_horaire] - bioenergies_horaire.iloc[tranche_horaire] - previous_nucbase - previous_nucflex - previous_coal - previous_fuel - previous_gasCC + previous_export - previous_import)
            variation_need = float(variation_need)

            #### Si pas besoin de variation; on ne change rien ###
            if variation_need == 0 :  
                
                coal[tranche_horaire] = previous_coal
                fuel[tranche_horaire] = previous_fuel
                gasCC[tranche_horaire] = previous_gasCC
                nucflex[tranche_horaire] = previous_nucflex
                nucbase[tranche_horaire] = previous_nucbase
                import_[tranche_horaire] = previous_import
                export[tranche_horaire] = previous_export
                effacement[tranche_horaire] = variation_need

            ### Excès de production ###
            if variation_need < 0 :

                decrease_need = -variation_need

                #Charbon
                if previous_coal - (max_coal * ramp_coal) >= min_coal : 
                    decrease_capacity_coal = max_coal * ramp_coal
                else :
                    decrease_capacity_coal = previous_coal - min_coal

                #Pétrole
                if fuel_variation[tranche_horaire] == True :
                    if previous_fuel - (max_fuel * ramp_fuel) >= min_fuel :
                        decrease_capacity_fuel = max_fuel * ramp_fuel
                    else :
                        decrease_capacity_fuel = previous_fuel - min_fuel
                else :
                    decrease_capacity_fuel = 0

                #Gaz
                if gasCC_variation2[tranche_horaire] == True :
                    if previous_gasCC - (max_gasCC * ramp_gasCC) >= min_gasCC :
                        decrease_capacity_gasCC = max_gasCC * ramp_gasCC
                    else :
                        decrease_capacity_gasCC = previous_gasCC - min_gasCC
                else :
                    decrease_capacity_gasCC = 0

                #Pompes à eau 
                if storagecharge_variation == True :
                    if max_stock - stock >= max_charge :
                        storage_capacity = max_charge
                    else :
                        if max_stock - stock > 0 :
                            storage_capacity = (max_stock - stock)
                        else :
                            storage_capacity = 0
                else :
                    storage_capacity = 0

                #Thermique renouvelable
                if storagecharge_variation_th == True :
                    if max_stock_th - stock_th >= max_charge_th :
                        storage_capacity_th = max_charge_th
                    else :
                        if max_stock_th - stock_th > 0 :
                            storage_capacity_th = (max_stock_th - stock_th)
                        else :
                            storage_capacity_th = 0
                else :
                    storage_capacity_th = 0

                #Nucléaire de pointe
                if nucflex_variation[tranche_horaire] == True :
                    if previous_nucflex - (max_nucflex * ramp_nucflex) >= min_nucflex :
                        decrease_capacity_nucflex = max_nucflex * ramp_nucflex
                    else :
                        decrease_capacity_nucflex = previous_nucflex - min_nucflex
                else :
                    decrease_capacity_nucflex = 0

                #Nucléaire de base 
                if previous_nucbase - (max_nucbase * ramp_nucbase) >= min_nucbase :
                    decrease_capacity_nucbase = max_nucbase * ramp_nucbase
                else:
                    decrease_capacity_nucbase = previous_nucbase - min_nucbase

                #Importaions 
                if import_variation[tranche_horaire] == True :
                    if previous_import - (Kimport * ramp_import) < 0 :
                        decrease_capacity_import = previous_import
                    else :
                        decrease_capacity_import = Kimport * ramp_import
                else :
                    if previous_import - (Kimport * ramp_import * 0.4) < 0 :
                        decrease_capacity_import = previous_import
                    else:
                        decrease_capacity_import = Kimport * ramp_import * 0.4

                #Exportations
                if export_variation[tranche_horaire] == True :
                    if previous_export + (Kexport * ramp_export) <= Kexport :
                        increase_capacity_export = Kexport * ramp_export
                    else :
                        increase_capacity_export = (Kexport - previous_export)
                else :
                    if previous_export + (Kexport * ramp_export * 0.4) <= Kexport :
                        increase_capacity_export = Kexport * ramp_export * 0.4
                    else :
                        increase_capacity_export = (Kexport - previous_export)

                
                #Ordre de préséance économique
                if (coût_gaz <= coût_fuel) and (coût_fuel <= coût_coal) : #Gaz < Petrole < Charbon
                    previous_ordre1 = previous_gasCC
                    previous_ordre2 = previous_fuel
                    previous_ordre3 = previous_coal
                    decrease_capacity_ordre1 = decrease_capacity_gasCC
                    decrease_capacity_ordre2 = decrease_capacity_fuel
                    decrease_capacity_ordre3 = decrease_capacity_coal
                else :
                    if (coût_coal <= coût_gaz) and (coût_gaz <= coût_fuel) : #Charbon < Gaz < Pétrole
                        previous_ordre1 = previous_coal
                        previous_ordre2 = previous_gasCC
                        previous_ordre3 = previous_fuel
                        decrease_capacity_ordre1 = decrease_capacity_coal
                        decrease_capacity_ordre2 = decrease_capacity_gasCC
                        decrease_capacity_ordre3 = decrease_capacity_fuel
                    else :                                                   #Gaz < Charbon < Pétrole
                        previous_ordre1 = previous_gasCC
                        previous_ordre2 = previous_coal
                        previous_ordre3 = previous_fuel
                        decrease_capacity_ordre1 = decrease_capacity_gasCC
                        decrease_capacity_ordre2 = decrease_capacity_coal
                        decrease_capacity_ordre3 = decrease_capacity_fuel

                if (maxbat - bat_stock >= rampbat * maxbat) :
                    bat_charge_capacity = rampbat * maxbat
                else : 
                    bat_charge_capacity = maxbat - bat_stock

                #Si effacement necessaire 
                if (decrease_need >= decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + increase_capacity_export + decrease_capacity_import + bat_charge_capacity) :
                    
                    effacement1[tranche_horaire] = -(decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + increase_capacity_export + decrease_capacity_import + bat_charge_capacity))
                    effacement[tranche_horaire] = -(decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + increase_capacity_export + decrease_capacity_import + bat_charge_capacity))

                    ordre1 = previous_ordre1 - decrease_capacity_ordre1
                    ordre2 = previous_ordre2 - decrease_capacity_ordre2
                    ordre3 = previous_ordre3 - decrease_capacity_ordre3

                    storage_charge[tranche_horaire] = storage_capacity
                    stock = stock + storage_charge[tranche_horaire] * 0.8

                    storage_charge_th[tranche_horaire] = storage_capacity_th
                    stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8
                    
                    bat_charge[tranche_horaire] = bat_charge_capacity
                    bat_stock = bat_stock + bat_charge[tranche_horaire]

                    nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                    nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                    import_[tranche_horaire] = previous_import - decrease_capacity_import
                    export[tranche_horaire] = previous_export + increase_capacity_export

                #Si export suffisant
                else :
                    if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + decrease_capacity_import + bat_charge_capacity) :
                        ordre1 = previous_ordre1 - decrease_capacity_ordre1
                        ordre2 = previous_ordre2 - decrease_capacity_ordre2
                        ordre3 = previous_ordre3 - decrease_capacity_ordre3

                        storage_charge[tranche_horaire] = storage_capacity
                        stock = stock + storage_charge[tranche_horaire] * 0.8

                        storage_charge_th[tranche_horaire] = storage_capacity_th
                        stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                        bat_charge[tranche_horaire] = bat_charge_capacity
                        bat_stock = bat_stock + bat_charge[tranche_horaire]

                        nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                        nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                        import_[tranche_horaire] = previous_import - decrease_capacity_import
                        export[tranche_horaire] = previous_export + decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + decrease_capacity_import + bat_charge_capacity)
                    
                    #Si storage suffisant
                    else :
                        if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity_th + decrease_capacity_import + decrease_capacity_nucflex + decrease_capacity_nucbase + bat_charge_capacity) :
                            ordre1 = previous_ordre1 - decrease_capacity_ordre1
                            ordre2 = previous_ordre2 - decrease_capacity_ordre2
                            ordre3 = previous_ordre3 - decrease_capacity_ordre3

                            storage_charge[tranche_horaire] = decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + storage_capacity_th + decrease_capacity_nucflex + decrease_capacity_nucbase + decrease_capacity_import + bat_charge_capacity)
                            stock = stock + storage_charge[tranche_horaire] * 0.8

                            storage_charge_th[tranche_horaire] = storage_capacity_th
                            stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                            bat_charge[tranche_horaire] = bat_charge_capacity
                            bat_stock = bat_stock + bat_charge[tranche_horaire]

                            nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                            nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                            import_[tranche_horaire] = previous_import - decrease_capacity_import
                            export[tranche_horaire] = previous_export 

                            #Si thermique renouvelable est suffisant
                        else :
                            if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_import + decrease_capacity_nucflex + decrease_capacity_nucbase + bat_charge_capacity) :
                                ordre1 = previous_ordre1 - decrease_capacity_ordre1
                                ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                storage_charge[tranche_horaire] = 0
                                stock = stock + storage_charge[tranche_horaire] * 0.8

                                storage_charge_th[tranche_horaire] = decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex + decrease_capacity_nucbase + decrease_capacity_import + bat_charge_capacity)
                                stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                bat_charge[tranche_horaire] = bat_charge_capacity
                                bat_stock = bat_stock + bat_charge[tranche_horaire]

                                nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                                nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                                import_[tranche_horaire] = previous_import - decrease_capacity_import
                                export[tranche_horaire] = previous_export 

                            #Imports
                            else :
                                if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex + decrease_capacity_nucbase + bat_charge_capacity) :
                                    ordre1 = previous_ordre1 - decrease_capacity_ordre1
                                    ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                    ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                    storage_charge[tranche_horaire] = 0
                                    stock = stock + storage_charge[tranche_horaire] * 0.8

                                    storage_charge_th[tranche_horaire] = 0
                                    stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                    bat_charge[tranche_horaire] = bat_charge_capacity
                                    bat_stock = bat_stock + bat_charge[tranche_horaire]

                                    nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                                    nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                                    import_[tranche_horaire] = previous_import - decrease_need + (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex + decrease_capacity_nucbase + bat_charge_capacity)
                                    export[tranche_horaire] = previous_export

                                #Batteries
                                else :
                                    if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex + decrease_capacity_nucbase) :
                                        ordre1 = previous_ordre1 - decrease_capacity_ordre1
                                        ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                        ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                        storage_charge[tranche_horaire] = 0
                                        stock = stock + storage_charge[tranche_horaire] * 0.8

                                        storage_charge_th[tranche_horaire] = 0
                                        stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                        bat_charge[tranche_horaire] = decrease_need - (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex + decrease_capacity_nucbase)
                                        bat_stock = bat_stock + bat_charge[tranche_horaire]

                                        nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                                        nucbase[tranche_horaire] = previous_nucbase - decrease_capacity_nucbase
                                        import_[tranche_horaire] = previous_import
                                        export[tranche_horaire] = previous_export

                                    #Nucléaire de base
                                    else : 
                                        if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex) :
                                            ordre1 = previous_ordre1 - decrease_capacity_ordre1
                                            ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                            ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                            storage_charge[tranche_horaire] = 0
                                            stock = stock + storage_charge[tranche_horaire] * 0.8

                                            storage_charge_th[tranche_horaire] = 0
                                            stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                            bat_charge[tranche_horaire] = 0
                                            bat_stock = bat_stock + bat_charge[tranche_horaire]

                                            nucflex[tranche_horaire] = previous_nucflex - decrease_capacity_nucflex
                                            nucbase[tranche_horaire] = previous_nucbase - decrease_need + (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1 + decrease_capacity_nucflex)
                                            import_[tranche_horaire] = previous_import
                                            export[tranche_horaire] = previous_export
                                        
                                        #Nucléaire de pointe
                                        else :
                                            if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1) :
                                                ordre1 = previous_ordre1 - decrease_capacity_ordre1
                                                ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                                ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                                storage_charge[tranche_horaire] = 0
                                                stock = stock + storage_charge[tranche_horaire] * 0.8

                                                storage_charge_th[tranche_horaire] = 0
                                                stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8
                                                
                                                bat_charge[tranche_horaire] = 0
                                                bat_stock = bat_stock + bat_charge[tranche_horaire]

                                                nucflex[tranche_horaire] = previous_nucflex - decrease_need + (decrease_capacity_ordre3 + decrease_capacity_ordre2 + decrease_capacity_ordre1)
                                                nucbase[tranche_horaire] = previous_nucbase
                                                import_[tranche_horaire] = previous_import
                                                export[tranche_horaire] = previous_export

                                            #Ordre 1
                                            else :
                                                if (decrease_need > decrease_capacity_ordre3 + decrease_capacity_ordre2) :
                                                    ordre1 = previous_ordre1 - decrease_need + (decrease_capacity_ordre3 + decrease_capacity_ordre2)
                                                    ordre2 = previous_ordre2 - decrease_capacity_ordre2
                                                    ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                                    storage_charge[tranche_horaire] = 0
                                                    stock = stock + storage_charge[tranche_horaire] * 0.8

                                                    storage_charge_th[tranche_horaire] = 0
                                                    stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                                    bat_charge[tranche_horaire] = 0
                                                    bat_stock = bat_stock + bat_charge[tranche_horaire]

                                                    nucflex[tranche_horaire] = previous_nucflex
                                                    nucbase[tranche_horaire] = previous_nucbase
                                                    import_[tranche_horaire] = previous_import
                                                    export[tranche_horaire] = previous_export

                                                #Ordre 2
                                                else :
                                                    if (decrease_need > decrease_capacity_ordre3) :
                                                        ordre1 = previous_ordre1
                                                        ordre2 = previous_ordre2 - decrease_need + (decrease_capacity_ordre3)
                                                        ordre3 = previous_ordre3 - decrease_capacity_ordre3

                                                        storage_charge[tranche_horaire] = 0
                                                        stock = stock + storage_charge[tranche_horaire] * 0.8

                                                        storage_charge_th[tranche_horaire] = 0
                                                        stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                                        bat_charge[tranche_horaire] = 0
                                                        bat_stock = bat_stock + bat_charge[tranche_horaire]

                                                        nucflex[tranche_horaire] = previous_nucflex
                                                        nucbase[tranche_horaire] = previous_nucbase
                                                        import_[tranche_horaire] = previous_import
                                                        export[tranche_horaire] = previous_export

                                                    #Ordre 3
                                                    else :
                                                        ordre1 = previous_ordre1
                                                        ordre2 = previous_ordre2
                                                        ordre3 = previous_ordre3 - decrease_need

                                                        storage_charge[tranche_horaire] = 0
                                                        stock = stock + storage_charge[tranche_horaire] * 0.8

                                                        storage_charge_th[tranche_horaire] = 0
                                                        stock_th = stock_th + storage_charge_th[tranche_horaire] * 0.8

                                                        bat_charge[tranche_horaire] = 0
                                                        bat_stock = bat_stock + bat_charge[tranche_horaire]

                                                        nucflex[tranche_horaire] = previous_nucflex
                                                        nucbase[tranche_horaire] = previous_nucbase
                                                        import_[tranche_horaire] = previous_import
                                                        export[tranche_horaire] = previous_export

                if (coût_gaz <= coût_fuel) and (coût_fuel <= coût_coal) :
                    gasCC[tranche_horaire] = ordre1
                    fuel[tranche_horaire] = ordre2
                    coal[tranche_horaire] = ordre3
                else :
                    if (coût_coal <= coût_gaz) and (coût_gaz <= coût_fuel) : 
                        coal[tranche_horaire] = ordre1
                        gasCC[tranche_horaire] = ordre2
                        fuel[tranche_horaire] = ordre3
                    else :
                        gasCC[tranche_horaire] = ordre1
                        coal[tranche_horaire] = ordre2
                        fuel[tranche_horaire] = ordre3

            ### Défaut de production ###              
            else : 
                increase_need = variation_need

                #Charbon 
                if (previous_coal + (max_coal * ramp_coal) >= max_coal) :
                    increase_capacity_coal = max_coal - previous_coal
                else : 
                    increase_capacity_coal = max_coal * ramp_coal

                #Pétrole
                if (previous_fuel + (max_fuel * ramp_fuel) >= max_fuel) :
                    increase_capacity_fuel = max_fuel - previous_fuel
                else :
                    increase_capacity_fuel = max_fuel * ramp_fuel

                if fuel_variation[tranche_horaire] == False :
                    increase_capacity_fuel = 0

                #GazCC
                if gasCC_variation[tranche_horaire] == True :
                    if (previous_gasCC + (max_gasCC * ramp_gasCC) >= max_gasCC) :
                        increase_capacity_gasCC = max_gasCC - previous_gasCC
                    else :
                        increase_capacity_gasCC = max_gasCC * ramp_gasCC
                else :
                    increase_capacity_gasCC = 0
                
                if gasCC_variation2[tranche_horaire] == False :
                    increase_capacity_gasCC = 0

                #Retenues d'eau
                if (storagedecharge_variation == True) :
                    if (stock > max_discharge) :
                        distorage_capacity = max_discharge
                    else :
                        if (stock > 0) :
                            distorage_capacity = stock
                        else :
                            distorage_capacity = 0
                else :
                    distorage_capacity = 0

                #thermique décarboné
                if (storagedecharge_variation_th == True) :
                    if (stock_th > max_discharge_th) :
                        distorage_capacity_th = max_discharge_th
                    else :
                        if (stock_th > 0) :
                            distorage_capacity_th = stock_th
                        else :
                            distorage_capacity_th = 0
                else :
                    distorage_capacity_th = 0

                #Nucléaire de pointe 
                if (previous_nucflex + (max_nucflex * ramp_nucflex) >= max_nucflex) :
                    increase_capacity_nucflex = max_nucflex - previous_nucflex
                else :
                    increase_capacity_nucflex = max_nucflex * ramp_nucflex

                #Nucléaire de base
                if (previous_nucbase + (max_nucbase * ramp_nucbase) >= max_nucbase) :
                    increase_capacity_nucbase = max_nucbase - previous_nucbase
                else :
                    increase_capacity_nucbase = max_nucbase * ramp_nucbase

                #Exports
                if (export_variation[tranche_horaire] == True) :
                    if (previous_export - (Kexport * ramp_export) >= 0) :
                        decrease_capacity_export = Kexport * ramp_export
                    else :
                        decrease_capacity_export = previous_export
                else :
                    if (previous_export - (Kexport * ramp_export * 0.4) >= 0) :
                        decrease_capacity_export = Kexport * ramp_export * 0.4
                    else :
                        decrease_capacity_export = previous_export

                #Imports 
                if (import_variation[tranche_horaire] == True) :
                    if (previous_import + (Kimport * ramp_import) >= Kimport) :
                        increase_capacity_import = Kimport - previous_import
                    else :
                        increase_capacity_import = Kimport * ramp_import
                else :
                    if (previous_import + (Kimport * ramp_import * 0.4) >= Kimport) :
                        increase_capacity_import = Kimport - previous_import
                    else :
                        increase_capacity_import = Kimport * ramp_import * 0.4

                #Ordre de préséance économique 
                if (coût_gaz <= coût_fuel) and (coût_fuel <= coût_coal) :
                    previous_ordre1 = previous_gasCC
                    previous_ordre2 = previous_fuel
                    previous_ordre3 = previous_coal
                    increase_capacity_ordre1 = increase_capacity_gasCC
                    increase_capacity_ordre2 = increase_capacity_fuel
                    increase_capacity_ordre3 = increase_capacity_coal
                else :
                    if (coût_coal <= coût_gaz) and (coût_gaz <= coût_fuel) :
                        previous_ordre1 = previous_coal
                        previous_ordre2 = previous_gasCC
                        previous_ordre3 = previous_fuel
                        increase_capacity_ordre1 = increase_capacity_coal
                        increase_capacity_ordre2 = increase_capacity_gasCC
                        increase_capacity_ordre3 = increase_capacity_fuel
                    else :
                        previous_ordre1 = previous_gasCC
                        previous_ordre2 = previous_coal
                        previous_ordre3 = previous_fuel
                        increase_capacity_ordre1 = increase_capacity_gasCC
                        increase_capacity_ordre2 = increase_capacity_coal
                        increase_capacity_ordre3 = increase_capacity_fuel
                
                #Batteries
                if (bat_stock - minbat >= rampbat * maxbat) :
                    bat_discharge_capacity = rampbat * maxbat
                else :
                    bat_discharge_capacity = bat_stock - minbat

            
                #Effacement
                if (increase_need >= increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + decrease_capacity_export + increase_capacity_import + bat_discharge_capacity) :
                    
                    effacement2[tranche_horaire] = increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + decrease_capacity_export + increase_capacity_import + bat_discharge_capacity)
                    effacement[tranche_horaire] = increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + decrease_capacity_export + increase_capacity_import + bat_discharge_capacity)

                    ordre1 = previous_ordre1 + increase_capacity_ordre1
                    ordre2 = previous_ordre2 + increase_capacity_ordre2
                    ordre3 = previous_ordre3 + increase_capacity_ordre3

                    storage_discharge[tranche_horaire] = distorage_capacity
                    stock = stock - storage_discharge[tranche_horaire]

                    storage_discharge_th[tranche_horaire] = distorage_capacity_th
                    stock_th = stock_th - storage_discharge_th[tranche_horaire]

                    bat_discharge[tranche_horaire] = bat_discharge_capacity
                    bat_stock = bat_stock - bat_discharge[tranche_horaire]

                    nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                    nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                    import_[tranche_horaire] = previous_import + increase_capacity_import
                    export[tranche_horaire] = previous_export - decrease_capacity_export

                #Importations
                else :
                    if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + decrease_capacity_export + bat_discharge_capacity) :
                        
                        ordre1 = previous_ordre1 + increase_capacity_ordre1
                        ordre2 = previous_ordre2 + increase_capacity_ordre2
                        ordre3 = previous_ordre3 + increase_capacity_ordre3

                        storage_discharge[tranche_horaire] = distorage_capacity
                        stock = stock - storage_discharge[tranche_horaire]

                        storage_discharge_th[tranche_horaire] = distorage_capacity_th
                        stock_th = stock_th - storage_discharge_th[tranche_horaire]

                        bat_discharge[tranche_horaire] = bat_discharge_capacity
                        bat_stock = bat_stock - bat_discharge[tranche_horaire]

                        nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                        nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                        import_[tranche_horaire] = previous_import + increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + decrease_capacity_export + bat_discharge_capacity)
                        export[tranche_horaire] = previous_export - decrease_capacity_export

                    #Exportations
                    else :
                        if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + bat_discharge_capacity) :
                            
                            ordre1 = previous_ordre1 + increase_capacity_ordre1
                            ordre2 = previous_ordre2 + increase_capacity_ordre2
                            ordre3 = previous_ordre3 + increase_capacity_ordre3

                            storage_discharge[tranche_horaire] = distorage_capacity
                            stock = stock - storage_discharge[tranche_horaire]

                            storage_discharge_th[tranche_horaire] = distorage_capacity_th
                            stock_th = stock_th - storage_discharge_th[tranche_horaire]

                            bat_discharge[tranche_horaire] = bat_discharge_capacity
                            bat_stock = bat_stock - bat_discharge[tranche_horaire]

                            nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                            nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                            import_[tranche_horaire] = previous_import
                            export[tranche_horaire] = previous_export - increase_need + (increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + bat_discharge_capacity)

                        #Batteries
                        else :
                            if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + distorage_capacity) :
                                
                                ordre1 = previous_ordre1 + increase_capacity_ordre1
                                ordre2 = previous_ordre2 + increase_capacity_ordre2
                                ordre3 = previous_ordre3 + increase_capacity_ordre3

                                storage_discharge[tranche_horaire] = distorage_capacity
                                stock = stock - storage_discharge[tranche_horaire]

                                storage_discharge_th[tranche_horaire] = distorage_capacity_th
                                stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                bat_discharge[tranche_horaire] = increase_need - (increase_capacity_nucflex + distorage_capacity_th + increase_capacity_nucbase + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3 + distorage_capacity)
                                bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                import_[tranche_horaire] = previous_import
                                export[tranche_horaire] = previous_export
                            
                            #Retenues d'eau
                            else :
                                if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3) :
                                    
                                    ordre1 = previous_ordre1 + increase_capacity_ordre1
                                    ordre2 = previous_ordre2 + increase_capacity_ordre2
                                    ordre3 = previous_ordre3 + increase_capacity_ordre3

                                    storage_discharge[tranche_horaire] = increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + distorage_capacity_th + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3)
                                    stock = stock - storage_discharge[tranche_horaire]

                                    storage_discharge_th[tranche_horaire] = distorage_capacity_th
                                    stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                    bat_discharge[tranche_horaire] = 0
                                    bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                    nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                    nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                    import_[tranche_horaire] = previous_import
                                    export[tranche_horaire] = previous_export

                                #Thermique renouvelable
                                else :
                                    if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3) :
                                        
                                        ordre1 = previous_ordre1 + increase_capacity_ordre1
                                        ordre2 = previous_ordre2 + increase_capacity_ordre2
                                        ordre3 = previous_ordre3 + increase_capacity_ordre3

                                        storage_discharge[tranche_horaire] = 0
                                        stock = stock - storage_discharge[tranche_horaire]

                                        storage_discharge_th[tranche_horaire] = increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1 + increase_capacity_ordre2 + increase_capacity_ordre3)
                                        stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                        bat_discharge[tranche_horaire] = 0
                                        bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                        nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                        nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                        import_[tranche_horaire] = previous_import
                                        export[tranche_horaire] = previous_export

                                    #Ordre 3
                                    else :
                                        if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1 + increase_capacity_ordre2) :
                                            
                                            ordre1 = previous_ordre1 + increase_capacity_ordre1
                                            ordre2 = previous_ordre2 + increase_capacity_ordre2
                                            ordre3 = previous_ordre3 + increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1 + increase_capacity_ordre2)

                                            storage_discharge[tranche_horaire] = 0
                                            stock = stock - storage_discharge[tranche_horaire]

                                            storage_discharge_th[tranche_horaire] = 0
                                            stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                            bat_discharge[tranche_horaire] = 0
                                            bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                            nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                            nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                            import_[tranche_horaire] = previous_import
                                            export[tranche_horaire] = previous_export

                                        #Ordre 2
                                        else :
                                            if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1) :
                                                
                                                ordre1 = previous_ordre1 + increase_capacity_ordre1
                                                ordre2 = previous_ordre2 + increase_need - (increase_capacity_nucflex + increase_capacity_nucbase + increase_capacity_ordre1)
                                                ordre3 = previous_ordre3

                                                storage_discharge[tranche_horaire] = 0
                                                stock = stock - storage_discharge[tranche_horaire]

                                                storage_discharge_th[tranche_horaire] = 0
                                                stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                                bat_discharge[tranche_horaire] = 0
                                                bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                                nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                                nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                                import_[tranche_horaire] = previous_import
                                                export[tranche_horaire] = previous_export

                                            #Ordre 1
                                            else :
                                                if (increase_need > increase_capacity_nucflex + increase_capacity_nucbase) :
                                                    
                                                    ordre1 = previous_ordre1 + increase_need - (increase_capacity_nucflex + increase_capacity_nucbase)
                                                    ordre2 = previous_ordre2
                                                    ordre3 = previous_ordre3

                                                    storage_discharge[tranche_horaire] = 0
                                                    stock = stock - storage_discharge[tranche_horaire]

                                                    storage_discharge_th[tranche_horaire] = 0
                                                    stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                                    bat_discharge[tranche_horaire] = 0
                                                    bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                                    nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                                    nucbase[tranche_horaire] = previous_nucbase + increase_capacity_nucbase
                                                    import_[tranche_horaire] = previous_import
                                                    export[tranche_horaire] = previous_export

                                                #Nucléaire de base
                                                else :
                                                    if (increase_need > increase_capacity_nucflex) :
                                                        
                                                        ordre1 = previous_ordre1
                                                        ordre2 = previous_ordre2
                                                        ordre3 = previous_ordre3

                                                        storage_discharge[tranche_horaire] = 0
                                                        stock = stock - storage_discharge[tranche_horaire]

                                                        storage_discharge_th[tranche_horaire] = 0
                                                        stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                                        bat_discharge[tranche_horaire] = 0
                                                        bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                                        nucflex[tranche_horaire] = previous_nucflex + increase_capacity_nucflex
                                                        nucbase[tranche_horaire] = previous_nucbase + increase_need - (increase_capacity_nucflex)
                                                        import_[tranche_horaire] = previous_import
                                                        export[tranche_horaire] = previous_export


                                                    else :
                                                        
                                                        ordre1 = previous_ordre1
                                                        ordre2 = previous_ordre2
                                                        ordre3 = previous_ordre3

                                                        storage_discharge[tranche_horaire] = 0
                                                        stock = stock - storage_discharge[tranche_horaire]

                                                        storage_discharge_th[tranche_horaire] = 0
                                                        stock_th = stock_th - storage_discharge_th[tranche_horaire]

                                                        bat_discharge[tranche_horaire] = 0
                                                        bat_stock = bat_stock - bat_discharge[tranche_horaire]

                                                        nucflex[tranche_horaire] = previous_nucflex + increase_need
                                                        nucbase[tranche_horaire] = previous_nucbase
                                                        import_[tranche_horaire] = previous_import
                                                        export[tranche_horaire] = previous_export

                if (coût_gaz <= coût_fuel) and (coût_fuel <= coût_coal) :
                    gasCC[tranche_horaire] = ordre1
                    fuel[tranche_horaire] = ordre2
                    coal[tranche_horaire] = ordre3
                else :
                    if (coût_coal <= coût_gaz) and (coût_gaz <= coût_fuel) :
                        coal[tranche_horaire] = ordre1
                        gasCC[tranche_horaire] = ordre2
                        fuel[tranche_horaire] = ordre3
                    else : 
                        gasCC[tranche_horaire] = ordre1
                        coal[tranche_horaire] = ordre2
                        fuel[tranche_horaire] = ordre3


            #Définition des périodes de stabilisation nécessaires
            if (previous_nucflex > 0) :
                if ((nucflex[tranche_horaire] / previous_nucflex) < 1) :
                    if ((nucflex[tranche_horaire] / previous_nucflex) > 0.6) :
                        nucflex_variation[tranche_horaire + 1] = False
                    else :
                        nucflex_variation[tranche_horaire + 1] = False
                        nucflex_variation[tranche_horaire + 2] = False
                        nucflex_variation[tranche_horaire + 3] = False
                        nucflex_variation[tranche_horaire + 4] = False

            if (gasCC[tranche_horaire] > 0.9 * max_gasCC) :
                gasCC_variation2[tranche_horaire + 5] = False
                gasCC_variation2[tranche_horaire + 6] = False
                gasCC_variation2[tranche_horaire + 7] = False
                gasCC_variation2[tranche_horaire + 8] = False
                gasCC_variation2[tranche_horaire + 9] = False
                gasCC_variation2[tranche_horaire + 10] = False

            if (fuel[tranche_horaire] > max_fuel * 0.7) :
                fuel_variation[tranche_horaire + 4] = False
                fuel_variation[tranche_horaire + 5]  = False
                fuel_variation[tranche_horaire + 6]  = False
                fuel_variation[tranche_horaire + 7]  = False
                fuel_variation[tranche_horaire + 9]  = False
                fuel_variation[tranche_horaire + 10]  = False
                fuel_variation[tranche_horaire + 11]  = False
                fuel_variation[tranche_horaire + 12]  = False
                fuel_variation[tranche_horaire + 13]  = False
                fuel_variation[tranche_horaire + 14]  = False

            if (import_[tranche_horaire] - previous_import > 0.5 * ramp_import * Kimport) or (import_[tranche_horaire] - previous_import < (-0.5 * ramp_import * Kimport)) :
                import_variation[tranche_horaire + 1] = False
                import_variation[tranche_horaire + 2] = False
                #import_variation[tranche_horaire + 3] = False

            if (export[tranche_horaire] - previous_export > 0.5 * ramp_export * Kexport) or (export[tranche_horaire] - previous_export < -0.5 * ramp_export * Kexport) :
                export_variation[tranche_horaire + 1] = False
                export_variation[tranche_horaire + 2] = False
                #export_variation[tranche_horaire + 3] = False

            if (((8759 - tranche_horaire) * max_discharge * 0.1) < (stock - max_stock * 0.5)) :
                storagecharge_variation = False
            else :
                storagecharge_variation = True

            if (((8759 - tranche_horaire) * max_charge * 0.07) < (max_stock * 0.5 - stock)) :
                storagedecharge_variation = False
            else :
                storagedecharge_variation = True

            batterie = bat_charge[tranche_horaire] + bat_discharge[tranche_horaire]

            previous_coal = coal[tranche_horaire]
            previous_fuel = fuel[tranche_horaire]
            previous_gasCC = gasCC[tranche_horaire]
            previous_nucflex = nucflex[tranche_horaire]
            previous_nucbase = nucbase[tranche_horaire]
            previous_import = import_[tranche_horaire]
            previous_export = export[tranche_horaire]
            previous_bat = batterie 

            effacement[tranche_horaire] = conso_horaire_flex[tranche_horaire] + pertes[tranche_horaire] - hydro_horaire.iloc[tranche_horaire] - PV_horaire.iloc[tranche_horaire] - windon_horaire.iloc[tranche_horaire] - windoffT[tranche_horaire] - bioenergies_horaire.iloc[tranche_horaire] - coal[tranche_horaire] - fuel[tranche_horaire] - gasCC[tranche_horaire] - nucflex[tranche_horaire] - nucbase[tranche_horaire] - import_[tranche_horaire] + export[tranche_horaire] + storage_charge[tranche_horaire] - storage_discharge[tranche_horaire] + storage_charge_th[tranche_horaire] - storage_discharge_th[tranche_horaire] + bat_charge[tranche_horaire] - bat_discharge[tranche_horaire]
            
            #Quantité d'Energie Renouvelable
            QER = PV_horaire.iloc[tranche_horaire] + windon_horaire.iloc[tranche_horaire] + windoffT[tranche_horaire]

            #Ordre d'effacement des EnR
            if (ordre == 1) :
                tech1[tranche_horaire] = PV_horaire.iloc[tranche_horaire]
                tech2[tranche_horaire] = windon_horaire.iloc[tranche_horaire]
                tech3[tranche_horaire] = windoffT.iloc[tranche_horaire]
            else :
                if (ordre == 2) :
                    tech1[tranche_horaire] = windon_horaire.iloc[tranche_horaire]
                    tech2[tranche_horaire] = windoffT[tranche_horaire]
                    tech3[tranche_horaire] = PV_horaire.iloc[tranche_horaire]
                else :
                    if (ordre == 3) :
                        tech1[tranche_horaire] = windoffT.iloc[tranche_horaire]
                        tech2[tranche_horaire] = windon_horaire.iloc[tranche_horaire]
                        tech3[tranche_horaire] = PV_horaire.iloc[tranche_horaire]
                    else :
                        if (ordre == 4) :
                            tech1[tranche_horaire] = PV_horaire.iloc[tranche_horaire]
                            tech2[tranche_horaire] = windoffT[tranche_horaire]
                            tech3[tranche_horaire] = windon_horaire.iloc[tranche_horaire]
                        #Au prorata de la production
                        else : 
                            #Excès de production
                            if (effacement[tranche_horaire] < 0) : 
                                PV_curtailment[tranche_horaire] = -effacement[tranche_horaire] * (PV_horaire.iloc[tranche_horaire] / QER)
                                windon_curtailment[tranche_horaire] = -effacement[tranche_horaire] * (windon_horaire.iloc[tranche_horaire] / QER)
                                windoff_curtailment[tranche_horaire] = -effacement[tranche_horaire] * (windoffT[tranche_horaire] / QER)
                            #Défaut de production
                            else :
                                PV_curtailment[tranche_horaire] = 0
                                windon_curtailment[tranche_horaire] = 0
                                windoff_curtailment[tranche_horaire] = 0

            #Si excès de production
            if effacement[tranche_horaire] < 0 :
                #Tech1 suffit
                if (tech1[tranche_horaire] > - effacement[tranche_horaire]) :
                    tech1_curtailment[tranche_horaire] = - effacement[tranche_horaire]
                    tech2_curtailment[tranche_horaire] = 0
                    tech3_curtailment[tranche_horaire] = 0
                else :
                    #Tech1 et Tech2 suffisent
                    if (tech1[tranche_horaire] + tech2[tranche_horaire] > - effacement[tranche_horaire]) :
                        tech1_curtailment[tranche_horaire] = tech1[tranche_horaire]
                        tech2_curtailment[tranche_horaire] = - effacement[tranche_horaire] - tech1[tranche_horaire]
                        tech3_curtailment[tranche_horaire] = 0
                    else : 
                        #Tech1 et Tech2 et Tech3 suffisent
                        if (tech1[tranche_horaire] + tech2[tranche_horaire] + tech3[tranche_horaire] > - effacement[tranche_horaire]) :
                            tech1_curtailment[tranche_horaire] = tech1[tranche_horaire]
                            tech2_curtailment[tranche_horaire] = tech2[tranche_horaire]
                            tech3_curtailment[tranche_horaire] = - effacement[tranche_horaire] - tech1[tranche_horaire] - tech2[tranche_horaire]
                        #On efface les trois technologies
                        else :
                            tech1_curtailment[tranche_horaire] = tech1[tranche_horaire]
                            tech2_curtailment[tranche_horaire] = tech2[tranche_horaire]
                            tech3_curtailment[tranche_horaire] = tech3[tranche_horaire]
            else :
                tech1_curtailment[tranche_horaire] = 0
                tech2_curtailment[tranche_horaire] = 0
                tech3_curtailment[tranche_horaire] = 0

            
            if ordre == 1 :
                PV_curtailment[tranche_horaire] = tech1_curtailment[tranche_horaire]
                windon_curtailment[tranche_horaire] = tech2_curtailment[tranche_horaire]
                windoff_curtailment[tranche_horaire] = tech3_curtailment[tranche_horaire]
            else :
                if ordre == 2 :
                    PV_curtailment[tranche_horaire] = tech3_curtailment[tranche_horaire]
                    windon_curtailment[tranche_horaire] = tech1_curtailment[tranche_horaire]
                    windoff_curtailment[tranche_horaire] = tech2_curtailment[tranche_horaire]
                else :
                    if ordre == 3 :
                        PV_curtailment[tranche_horaire] = tech3_curtailment[tranche_horaire]
                        windon_curtailment[tranche_horaire] = tech2_curtailment[tranche_horaire]
                        windoff_curtailment[tranche_horaire] = tech1_curtailment[tranche_horaire]
                    else :
                        if ordre== 4 :
                            PV_curtailment[tranche_horaire] = tech1_curtailment[tranche_horaire]
                            windon_curtailment[tranche_horaire] = tech3_curtailment[tranche_horaire]
                            windoff_curtailment[tranche_horaire] = tech2_curtailment[tranche_horaire]

            pertes[tranche_horaire] += (nucbase[tranche_horaire] + nucflex[tranche_horaire] + coal[tranche_horaire] + gasCC[tranche_horaire] + fuel[tranche_horaire] + import_[tranche_horaire]) * perte

            if maxbat > 0 :
                stocks[tranche_horaire] = bat_stock / maxbat

            col39.append(stocks[tranche_horaire])

            if effacement[tranche_horaire] < -0.5 :
                v_excess += effacement[tranche_horaire]
                nb_excess += 1
            else :
                if effacement[tranche_horaire] > 0.5 :
                    v_lack += - effacement[tranche_horaire]
                    nb_lack += 1

            variation_need_list.append(variation_need)

    prodwindoffT = sum(windoffT) / 1000000
    prodT = (sum(nucbase) + sum(nucflex) + sum(gasCC) + sum(fuel) + sum(coal) + sum(hydro_horaire) + sum(PV_horaire) + sum(windon_horaire) + sum(bioenergies_horaire)) / 1000000
    prodT += prodwindoffT

    df_simulateur = pd.DataFrame(columns=['technologie', 'production (TWh)', 'taux_utilisation'])

    df_simulateur['technologie'] = ['nucléaire base',
                                    'nucléaire flexible',
                                    'gaz cycle combinés + TC',
                                    'charbon',
                                    'pétrole',
                                    'bioenergies',
                                    'hydraulique',
                                    'éolien terrestre',
                                    'photovoltaïque',
                                    'importations',
                                    'exportations',
                                    'pompage (STEP)',
                                    'énergie déversée (STEP)',
                                    'stock STEP 01/01',
                                    'stock STEP 31/12']

    prod = [sum(nucbase) / 1000000,
            sum(nucflex) / 1000000,
            sum(gasCC) / 1000000,
            sum(coal) / 1000000,
            sum(fuel) / 1000000,
            sum(bioenergies_horaire) / 1000000,
            sum(hydro_horaire) / 1000000,
            sum(windon_horaire) / 1000000,
            sum(PV_horaire) / 1000000,
            sum(import_) / 1000000, 
            sum(export) / 1000000, 
            sum(storage_charge) / 1000000, 
            sum(storage_discharge) / 1000000,
            max_stock / 2000000,
            stock / 1000000]

    df_simulateur['production (TWh)'] = [round(num, 1) for num in prod]

    if Kcoal > 0 :
        taux_utilisation_charbon = prod[3] * 1000000 / (Kcoal * 8760)
    else :
        taux_utilisation_charbon = None

    if Kfuel > 0 :
        taux_utilisation_petrole = prod[4] * 1000000 / (Kfuel * 8760)
    else :
        taux_utilisation_petrole = None

    if Knucbase == 0 :
        df_simulateur['taux_utilisation'] = [0,
                                            0,
                                            prod[2] *  1000000 / (KgasCC * 8760),
                                            taux_utilisation_charbon,
                                            taux_utilisation_petrole,
                                            prod[5] *  1000000 / (Kbiomas * 8760),
                                            prod[6] *  1000000 / (Khydro * 8760),
                                            prod[7] *  1000000 / (Kwindon * 8760),
                                            prod[8] *  1000000 / (KPV * 8760),
                                            prod[9] *  1000000 / (Kimport * 8760),
                                            prod[10] *  1000000 / (Kexport * 8760),
                                            prod[11] *  1000000 / (max_charge * 8760),
                                            prod[12] *  1000000 / (max_discharge * 8760),
                                            None,
                                            None]
    else :
        df_simulateur['taux_utilisation'] = [prod[0] * 1000000 / (Knucbase * 8760),
                                            prod[1] * 1000000 / (Knucflex * 8760),
                                            prod[2] *  1000000 / (KgasCC * 8760),
                                            taux_utilisation_charbon,
                                            taux_utilisation_petrole,
                                            prod[5] *  1000000 / (Kbiomas * 8760),
                                            prod[6] *  1000000 / (Khydro * 8760),
                                            prod[7] *  1000000 / (Kwindon * 8760),
                                            prod[8] *  1000000 / (KPV * 8760),
                                            prod[9] *  1000000 / (Kimport * 8760),
                                            prod[10] *  1000000 / (Kexport * 8760),
                                            prod[11] *  1000000 / (max_charge * 8760),
                                            prod[12] *  1000000 / (max_discharge * 8760),
                                            None,
                                            None]

    df_simulateur['taux_utilisation'] = round(df_simulateur['taux_utilisation']  * 100, 1)

    effacement_potentiel = {'solaire' : round(sum(PV_curtailment) / 1000000, 2),
                        'éolien onshore' : round(sum(windon_curtailment) / 1000000, 2),
                        'éolien offshore' : round(sum(windoff_curtailment) / 1000000, 2),
                        
                        'part_prod_solaire' : round(sum(PV_curtailment) / sum(PV_horaire), 3),
                        'part_prod_eolineon' : round(sum(windon_curtailment) / sum(windon_horaire), 3),
                        'part_prod_eolienoff' : round(sum(windoff_curtailment) / (prodwindoffT * 1000000), 3)
                        }
    effacement_potentiel = {key: round(float(value), 2) for key, value in effacement_potentiel.items()}

    desequilibre = {'exces_offre' : v_excess / -1000000,
                    "manque d'offre": v_lack / -1000000,
                    'frq_annuelle_exces' : nb_excess,
                    'frq_annuelle_manque' : nb_lack,
                    'part_prod_exces' :  v_excess / (-10000 * prodT),
                    'part_prod_manque' : v_lack / (-10000 * prodT)}
    desequilibre = {key: round(float(value), 2) for key, value in desequilibre.items()}

    parc_batterie_prod = round(sum(bat_discharge) / 1000000, 2)

    col40=[]
    cycle_discharge = 0
    cycle_charge = 0
    nbcycles = 0
    cycle20bis = 0
    cycle20 = 0
    cycle40 = 0
    cycle60 = 0
    cycle80 = 0
    cycle100 = 0

    cycle100bis, cycle80bis, cycle60bis, cycle40bis, cycle20bis = 0, 0, 0, 0, 0

    for i in range(8760) :
        if i == 0 :
            cycles[i] = 0
            col40.append(cycles[i])
        else :
            cycles[i] = stocks[i] - stocks[i-1]
            col40.append(cycles[i])

    cycle = [0]*8760

    cycle[0] = True
    n = 1
    for i in range(1, 8760):
        if cycle[i - 1] :
            if cycles[i] < 0 :
                cycle[i] = False
            else :
                cycle[i] = True
        else :
            if cycles[i] > 0 :
                cycle[i] = True
            else :
                cycle[i] = False

    for i in range(8759) :
        if cycle[i] :
            if cycle[i + 1] :
                cycle_charge = cycle_charge + cycles[i]
            else :
                cycle_charge += + cycles[i]
                nbcycles = nbcycles + cycle_charge
                if cycle_charge > 0.8 :
                    cycle100 = cycle100 + 1
                else :
                    if cycle_charge > 0.6 :
                        cycle80 = cycle80 + 1
                    else :
                        if cycle_charge > 0.4 :
                            cycle60 = cycle60 + 1
                        else :
                            if cycle_charge > 0.2 :
                                cycle40 = cycle40 + 1
                            else :
                                cycle20 = cycle20 + 1
                
                cycle_charge = 0

            if not cycle[i + 1] :
                cycle_discharge = cycle_discharge + cycles[i]
            else :
                cycle_discharge = cycle_discharge + cycles[i]
                nbcycles -= cycle_discharge

                if cycle_discharge < -0.8 :
                    cycle100bis += 1
                else :
                    if cycle_discharge < -0.6 :
                        cycle80bis += 1
                    else :
                        if cycle_discharge < -0.4 :
                            cycle60bis += 1
                        else :
                            if cycle_discharge < -0.2 :
                                cycle40bis += 1
                            else :
                                cycle20bis += 1
                
                cycle_discharge = 0

    df_scenario_simule = pd.DataFrame(columns=['date_heure', 'date', 'heure', 'effacement', 'total éolien offshore', 'consommation', 'nucléaire base', 'nucléaire flexible', 'hydraulique', 'PV', 'éolien onshore', 'bioénergies', 'charbon', 'gaz', 'pétrole', 'importations', 'exportations', 'soldes échanges', 'STEP décharge', 'STEP charge', 'thermique décharge', 'thermique charge', 'effacement potentiel PV', 'effacement potentiel éolien onshore', 'effacemet potentiel éolien offshore', 'batterie décharge', 'batterie charge', 'pertes', 'variation nécessaire', 'stock batteries'])

    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')

    # Générer la série 'heure' : toutes les heures de la journée
    heures = [f"{hour:02}:00" for hour in range(24)]

    # Créer toutes les combinaisons de dates et heures
    date_heure_combinations = list(itertools.product(dates, heures))

    # Extraire les colonnes séparément
    date_series = pd.Series([comb[0] for comb in date_heure_combinations], name='date')
    heure_series = pd.Series([comb[1] for comb in date_heure_combinations], name='heure')


    date_heure_formatted = [f"{comb[0].strftime('%Y-%m-%d')}-{comb[1][:2]}" for comb in date_heure_combinations]

    # Créer la DataFrame
    date_heure = pd.Series(date_heure_formatted)

    df_scenario_simule['date'] = date_series
    df_scenario_simule['heure'] = heure_series
    df_scenario_simule['effacement'] = effacement
    df_scenario_simule['total éolien offshore'] = windoffT
    df_scenario_simule['consommation'] = conso_horaire
    df_scenario_simule['nucléaire base'] = [x * (1 + perte) for x in nucbase]
    df_scenario_simule['nucléaire flexible'] = [x * (1 + perte) for x in nucflex]
    df_scenario_simule['hydraulique'] = hydro_horaire
    df_scenario_simule['PV'] = PV_horaire
    df_scenario_simule['éolien onshore'] = windon_horaire
    df_scenario_simule['bioénergies'] = bioenergies_horaire
    df_scenario_simule['charbon'] = [x * (1 + perte) for x in coal]
    df_scenario_simule['gaz'] = [x * (1 + perte) for x in gasCC]
    df_scenario_simule['pétrole'] = [x * (1 + perte) for x in fuel]
    df_scenario_simule['importations'] = [x * (1 + perte) for x in import_]
    df_scenario_simule['exportations'] = export
    df_scenario_simule['soldes échanges'] = df_scenario_simule['exportations'] - df_scenario_simule['importations']
    df_scenario_simule['STEP décharge'] = storage_discharge
    df_scenario_simule['STEP charge'] = storage_charge
    df_scenario_simule['thermique décharge'] = storage_discharge_th
    df_scenario_simule['thermique charge'] = storage_charge_th

    df_scenario_simule['effacement potentiel PV'] = PV_curtailment
    df_scenario_simule['effacement potentiel eolien onshore'] = windon_curtailment
    df_scenario_simule['effacemet potentiel eolien offshore'] = windoff_curtailment

    df_scenario_simule['batterie décharge'] = bat_discharge
    df_scenario_simule['batterie charge'] = bat_charge
    df_scenario_simule['pertes'] = pertes
    df_scenario_simule['variation nécessaire'] = variation_need_list
    df_scenario_simule['stock batteries'] =  col39

    df_scenario_simule['date_heure'] = date_heure

    return(df_simulateur, df_scenario_simule, effacement_potentiel, desequilibre, parc_batterie_prod, cycle100, cycle80, cycle60, cycle40, cycle20, cycle100bis, cycle80bis, cycle60bis, cycle40bis, cycle20bis)


def update_key():
    st.session_state.ramp_base_key += 1
    st.session_state.fc_base_key += 1

    st.session_state.ramp_flex_key += 1
    st.session_state.fc_flex_key += 1

    st.session_state.ramp_gaz_key += 1
    st.session_state.fc_gaz_key += 1

    st.session_state.ramp_coal_key += 1
    st.session_state.fc_coal_key += 1

    st.session_state.ramp_fuel_key += 1
    st.session_state.fc_fuel_key += 1

    st.session_state.ramp_import_key += 1
    st.session_state.ramp_export_key += 1

def update_key2():
    st.session_state.date_max_key += 1
    st.session_state.date_min_key += 1

if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

if "date_max_key" not in st.session_state:
    st.session_state.date_max_key = 0
if "date_min_key" not in st.session_state:
    st.session_state.date_min_key = 0

if "ramp_base_key" not in st.session_state:
    st.session_state.ramp_base_key = 0
if "fc_base_key" not in st.session_state:
    st.session_state.fc_base_key = 0

if "ramp_flex_key" not in st.session_state:
    st.session_state.ramp_flex_key = 0
if "fc_flex_key" not in st.session_state:
    st.session_state.fc_flex_key = 0

if "ramp_gaz_key" not in st.session_state:
    st.session_state.ramp_gaz_key = 0
if "fc_gaz_key" not in st.session_state:
    st.session_state.fc_gaz_key = 0

if "ramp_coal_key" not in st.session_state:
    st.session_state.ramp_coal_key = 0
if "fc_coal_key" not in st.session_state: 
    st.session_state.fc_coal_key = 0

if "ramp_fuel_key" not in st.session_state:
    st.session_state.ramp_fuel_key = 0
if "fc_fuel_key" not in st.session_state:
    st.session_state.fc_fuel_key = 0

if "ramp_import_key" not in st.session_state:
    st.session_state.ramp_import_key = 0
if "ramp_export_key" not in st.session_state:
    st.session_state.ramp_export_key = 0



st.session_state.perte = 7 / 100

# Configuration de la page
st.set_page_config(page_title="Simulation du système électrique français", layout="wide")

# Application du style CSS pour personnaliser l'apparence
st.markdown("""
    <style>
        .title {
            text-align: center;
            font-size: 40px;
            font-weight: bold;
            margin-top: -20px;
            margin-bottom: 60px;
        }
        .sidebar .sidebar-content {
            padding: 20px;
        }
        .stSelectbox, .stSlider {
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# Titre de la page
st.markdown('<div class="title"> Simulation du système électrique français </div>', unsafe_allow_html=True)

HORIZONTAL_RED = "image2.png"
logo = "image.png"

st.logo(HORIZONTAL_RED, icon_image=logo)


# Configuration de la sidebar
with st.sidebar:
    st.header("Paramètres de simulation :")
    
    with st.expander('### 🏭 Scénario de production', expanded=False):
        # Choix du scénario
        
        st.session_state.scenario_prod = st.radio(
            "Choisir un scénario RTE 2050 :",
            ["M0", "M1", "M23", "N1", "N2", "N03"],
            captions = ['100% renouvelable en 2050', 'Répartition diffuse', 'énergie renouvelable grands parcs', 'EnR et nouveau nucléaire 1', 'EnR et nouveau nucléaire 2', 'EnR et nouveau nucléaire 3'],
        )  

    scenarios_conso = {"réindustrialisation" : 752,
                  "sobriété" : 555,
                  "efficassité électrique moindre" : 714,
                  "électrification +" : 700,
                  "électrification -" : 578,
                  "Hydrogène +" : 754}

    with st.expander('### 💡 Scénario de consommation', expanded=False):
        # Choix du scénario
        st.session_state.scenario_conso = st.radio(
            "Choisir un scénario RTE 2050 :",
            ["réindustrialisation", "sobriété", "efficassité électrique moindre", "électrification +", "électrification -", "Hydrogène +"],
            captions = ['752 TWh', '555 TWh', '714 TWh', '700 TWh', '578 TWh', '754 TWh'],
            index=0,
        )

        st.session_state.conso_annuelle =  st.session_state.scenario_conso * 1000000 #MWh


    # Ordre d'effacement des EnR
    ordre_effacement_EnR = st.selectbox(
        "Ordre d'effacement des EnR",
        ("PV - éolien onshore - éolien offshore", 
         "éolien onshore - éolien offshore - PV", 
         "éolien offshore - éolien onshore - PV",
         "PV - éolien offshore - éolien onshore",
         "au prorata de la production")
    )

    st.header("Ressources :")

    col1_left, col2_left  = st.columns([1, 1])

    with col1_left :

        URL_STRING = "https://www.rte-france.com/analyses-tendances-et-prospectives/bilan-previsionnel-2050-futurs-energetiques"

        st.markdown(
            f'<a href="{URL_STRING}" style="display: inline-block; padding: 6px 10px; background-color: #00A6D9; color: white; text-align: center; text-decoration: none; border-radius: 7px;">infos scénarios</a>',
            unsafe_allow_html=True
        )

    with col2_left :
        st.button("'read me' file")



df_scenario = pd.read_csv('data_new\scenarios_RTE_Prod.csv', sep=';', header=0)
df_scenario['Bilan électrique (TWh)'] = df_scenario['Bilan électrique (TWh)'].astype('float32')
df_scenario['Parc installé (GW)'] = df_scenario['Parc installé (GW)'].astype('float32')
df_scenario['FC (%)'] = df_scenario['FC (%)'].astype('float32')
df_scenario['Ramping'] = df_scenario['Ramping'].astype('float32')
df_scenario['FC minimum (%)'] = df_scenario['FC minimum (%)'].astype('float32')

df_scenario = df_scenario[df_scenario['scénario'] == st.session_state.scenario_prod]

#Dataframe à afficher
df_scenario_plot = df_scenario.drop(columns=['Ramping', 'FC minimum (%)', 'scénario'])
df_scenario_plot['FC (%)'] = (df_scenario_plot['FC (%)'] * 100)
df_scenario_plot = df_scenario_plot.iloc[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15]]
emojis = ['☢️', '☢️', '🌬️', '🌬️', '☀️', '🌊', '🍃', '💧', '🏭', '🛢️', '🦫', '🔥', '🔋']

df_scenario_plot['Filière'] = [f"{emoji} {filiere}" for emoji, filiere in zip(emojis, df_scenario_plot['Filière'])]

#Données d'entrées modifiables par l'utilisateur
ramp_nucbase_ = 1
FC_min_nucbase_ = 30

ramp_nucflex_ = 15
FC_min_nucflex_ = 0

ramp_gaz_ = 40
FC_min_gaz_ = 0

ramp_coal_ = 60
FC_min_coal_ = 0

ramp_fuel_ = 30
FC_min_fuel_ = 5

ramp_import_ = 20
ramp_export_ = 25

 

# Disposition des colonnes principales
col1, col2 = st.columns([1, 1])


# Affichage des données et des éléments dans la première colonne
with col1:
    st.write("### Données de simulation")
    st.dataframe(df_scenario_plot, hide_index=True, height=492, use_container_width=True)



st.markdown("""
    <style>
        .stSlider {
            margin-top: -10px;
            margin-bottom: -10px;
        }
    </style>
""", unsafe_allow_html=True)

# Disposition des expander deux par deux sur une ligne
with col2:
    st.write("### Paramètres de production")

    # Deux expanders sur une ligne
    expander1, expander2 = st.columns(2)
    

    with expander1:
        # Nucléaire de base
        with st.expander('### Nucléaire de base', expanded=False):
            st.session_state.ramp_nucbase = st.select_slider(
                'Ramping :',
                options=range(101),
                value=1,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_base_{st.session_state.ramp_base_key}"
            )
            st.session_state.FC_min_nucbase = st.select_slider(
                'FC minimum :',
                options=range(101),
                value=30,
                format_func=lambda x: f'{x}%',
                key=f"slider_fc_base_{st.session_state.fc_base_key}"
            )
        # Charbon
        with st.expander('Charbon', expanded=False):
            st.session_state.ramp_coal = st.select_slider(
                'Ramping :',
                options=range(101),
                value=60,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_coal_{st.session_state.ramp_coal_key}"
            )
            st.session_state.FC_min_coal = st.select_slider(
                'FC minimum :',
                options=range(101),
                value=0,
                format_func=lambda x: f'{x}%',
                key=f"slider_fc_coal_{st.session_state.fc_coal_key}"
            )

        # gaz
        with st.expander('Gaz', expanded=False):
            st.session_state.ramp_gasCC = st.select_slider(
                'Ramping :',
                options=range(101),
                value=40,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_gaz_{st.session_state.ramp_gaz_key}"
            )
            st.session_state.FC_min_gasCC = st.select_slider(
                'FC minimum :',
                options=range(101),
                value=0,
                format_func=lambda x: f'{x}%',
                key=f"slider_fc_gaz_{st.session_state.fc_gaz_key}"
            )
        

    with expander2:
        # Nucléaire flexible
        with st.expander('Nucléaire flexible', expanded=False):
            st.session_state.ramp_nucflex = st.select_slider(
                'Ramping :',
                options=range(101),
                value=15,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_flex_{st.session_state.ramp_flex_key}"
            )
            st.session_state.FC_min_nucflex = st.select_slider(
                'FC minimum :',
                options=range(101),
                value=0,
                format_func=lambda x: f'{x}%',
                key=f"slider_fc_flex_{st.session_state.fc_flex_key}"
            )

        # Pétrole 
        with st.expander('Pétrole', expanded=True):
            st.session_state.ramp_fuel = st.select_slider(
                'Ramping :',
                options=range(101),
                value=30,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_fuel_{st.session_state.ramp_fuel_key}"
            )
            st.session_state.FC_min_fuel = st.select_slider(
                'FC minimum :',
                options=range(101),
                value=5,
                format_func=lambda x: f'{x}%',
                key=f"slider_fc_fuel_{st.session_state.fc_fuel_key}"
            )

    # Deuxième ligne d'expanders
    expander3, expander4 = st.columns(2)
    
    with expander3:
        # Imports
        with st.expander('Imports', expanded=True):
            st.write(f'Capacité : {39} GW')
            st.session_state.ramp_import = st.select_slider(
                'Ramping :',
                options=range(101),
                value=20,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_import_{st.session_state.ramp_import_key}"
            )

    with expander4:
        # Exports
        with st.expander('Exports', expanded=True):
            st.write(f'Capacité : {54.6} GW')
            st.session_state.ramp_export = st.select_slider(
                'Ramping :',
                options=range(101),
                value=25,
                format_func=lambda x: f'{x}%',
                key=f"slider_ramp_export_{st.session_state.ramp_export_key}"
            )
    _, col_middle, _ = st.columns([1, 2, 1])

    col1, col2,col3 = st.columns(3)
    with col2 :
        reset = st.button("réinitialiser", use_container_width = True, on_click=update_key)


if   st.session_state.button_clicked == False :
    if st.button("Lancer le simulateur", use_container_width=True):
        st.session_state.button_clicked = True  # Stocker l'état du clic

if st.session_state.button_clicked:

    df_simulateur, df_scenario_simule, effacement_potentiel, desequilibre, parc_batterie_prod, cycle100, cycle80, cycle60, cycle40, cycle20, cycle100bis, cycle80bis, cycle60bis, cycle40bis, cycle20bis = simulateur_systeme_electrique_francais(st.session_state.scenario_prod, st.session_state.scenario_conso, st.session_state.ramp_nucbase, st.session_state.FC_min_nucbase, st.session_state.ramp_coal, st.session_state.FC_min_coal, st.session_state.ramp_gasCC, st.session_state.FC_min_gasCC, st.session_state.ramp_nucflex, st.session_state.FC_min_nucflex, st.session_state.ramp_fuel, st.session_state.FC_min_fuel, st.session_state.ramp_import, st.session_state.ramp_export)

    df_results = df_scenario_simule.fillna('')

    # Conversion des colonnes en type datetime
    df_results['date_heure'] = pd.to_datetime(df_results['date_heure'], format='%Y-%m-%d-%H', errors='coerce')
    df_results['date_heure'] = df_results['date_heure'].apply(lambda x: x.replace(year=2050) if pd.notnull(x) else x)

    df_results['date'] = pd.to_datetime(df_results['date'], format='%Y-%m-%d', errors='coerce')
    # Définir la colonne 'date_heure' comme index
    df_results = df_results.set_index('date_heure')




    # Interface utilisateur avec Streamlit
    col1, col2 = st.columns([3, 2])

    with col1:
        # Multiselect pour choisir les colonnes
        colonnes_a_tracer = st.multiselect(
            "Choisissez les colonnes que vous voulez tracer :",
            options=df_results.columns[2:],
            default=[df_results.columns[3]]  # Par défaut, une seule colonne est sélectionnée
        )

    with col2:
        col1, col2, col3 = st.columns(3)

        min_date = df_results.index.min().date()  # Date minimale du dataframe
        max_date = df_results.index.max().date()  # Date maximale du dataframe

        with col1 : 
            date_debut = st.date_input("Date de début :", value=min_date, min_value=min_date, max_value=max_date, key=f"date_debut_{st.session_state.date_min_key}")
        with col2 :
            date_fin = st.date_input("Date de fin :", value=max_date, min_value=min_date, max_value=max_date, key=f"date_fin_{st.session_state.date_max_key}")
        with col3:
            st.write("") 
            st.button("Toutes les données", use_container_width = True, on_click=update_key2)
            

    # Vérification que l'utilisateur a sélectionné des colonnes
    if colonnes_a_tracer:
        # Filtrer le dataframe pour les colonnes sélectionnées et la plage de dates
        df_filtre = df_results[colonnes_a_tracer]
        df_filtre = df_filtre.loc[date_debut:date_fin]  # Filtrer par date

        if not df_filtre.empty:
            # Affichage du graphique
            st.line_chart(df_filtre, y_label="Energie en MWh")

        else:
            st.warning("Aucune donnée disponible pour la plage de dates sélectionnée.")
    else:
        st.warning("Veuillez sélectionner au moins un élément à tracer.")

    col1, col2 = st.columns([7, 1])
    with col2 :
        if st.button("Terminer", use_container_width=True):
            st.session_state.button_clicked = False
            st.rerun()
    