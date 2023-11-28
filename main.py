import sys, getopt
import argparse
from dotenv import load_dotenv
import os
import csv
import json
from argparse import Namespace



def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
                    prog = 'Retina Recalculation',
                    description = 'Recalculate Retina for manual input',
                    epilog = 'Devoteam')

    parser.add_argument('-t', '--type', help='The type of calculation: etalase or storefront', required=True)
    parser.add_argument('-f', '--file', help='The file to be processed', required=True)  
    parser.add_argument('-s', '--start', help='The starting row to be processed', required=False)  
    parser.add_argument('-n', '--number', help='The total number of rows to be processed', required=False)  
    
    args = parser.parse_args()
    if args.start == None:
        args.start = 1
    
    if args.number == None:
        args.number = -1

    csv = read_file(args.file)
    if csv != False:
        if args.type == "etalase":
            calculate_etalase(args, csv)
        else:
            calculate_storefront(args, csv)


def read_file(file_path):
    try:
        with open(file_path, 'r') as csvfile:
            # Create a CSV reader object with a header
            csv_reader = csv.DictReader(csvfile)
            data = [row for row in csv_reader]
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def calculate_etalase(args, csv):
    outlsetScoreObjects = []
    allEtalaseItems = []

    for row in csv:
        #print(row)
        id = row["id"]
        response = row["prediction"]
        response = response.replace("'", "\"")
        response = response.replace("True", "\"True\"")
        response = response.replace("False", "\"False\"")

        try:
            response = json.loads(response, object_hook=lambda d: Namespace(**d))
            
            if response.success == 'True':
                visibilityScores = response.payload_visibility.operators
                availabilityScores = response.payload_availability.operators
                outlsetScore = response.etalase_score
                outlsetScoreObject = create_outlet_score(outlsetScore, id, "etalase")
                outlsetScoreObjects.append(outlsetScoreObject)

                allEtalaseItems = mergeVisibilityAndAvailabilityScores(id, visibilityScores, availabilityScores, allEtalaseItems)

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(row)


    write_objects_to_csv(allEtalaseItems, "result-etalase-items.csv")
    write_objects_to_csv(outlsetScoreObjects, "result-etalase-outlet-scores.csv")


def create_outlet_score(outletScore, id, type):
    obj = argparse.Namespace()
    obj.tag = "recalculate"
    obj.outlet_score = outletScore
    obj.upload_file_id = id
    obj.scoring_type = type
    return obj

def create_etalase_item(visScore, avaScore, id):
    item = argparse.Namespace()
    item.operator = visScore.operator
    item.operatorText= avaScore.operatorText
    item.visibility_score= visScore.score
    item.visibility_percentage= visScore.percentage
    item.availability_score= avaScore.score
    item.availability_percentage= avaScore.percentage
    item.upload_file_id= id
    item.tag = "recalculate"
    return item

def mergeVisibilityAndAvailabilityScores(id, visibilityScores, availabilityScores, allEtalaseItems):
    results = [];
    for visScore in visibilityScores:
        for avaScore in availabilityScores:
            if visScore.operator.lower() == avaScore.operator.lower():
                item = create_etalase_item(visScore, avaScore, id)
                results.append(item)
                allEtalaseItems.append(item)
    return allEtalaseItems;

def calculate_storefront(args, csv):
    outlsetScoreObjects = []
    allStoreFrontItems = []
    allSqls = []

    for row in csv:
        #print(row)
        id = row["id"]
        response = row["prediction"]
        response = response.replace("'", "\"")
        response = response.replace("True", "\"True\"")
        response = response.replace("False", "\"False\"")

        try:
            response = json.loads(response, object_hook=lambda d: Namespace(**d))
            
            if response.success == 'True':
                operators = response.payload_visibility.operators
                outlsetScore = response.storefront_score
                outlsetScoreObject = create_outlet_score(outlsetScore, id, "storefront")
                outlsetScoreObjects.append(outlsetScoreObject)

                allStoreFrontItems = getStoreFrontItems(id, operators, allStoreFrontItems)
                largestOpObj = getTheLargestCoverageOperator(operators)
                largestOp = largestOpObj.operator
                largestOpText = operator2text(largestOp.lower())

                print("=======")
                print(largestOp)
                print(largestOpText)
                sql = "UPDATE uploadfile SET operatorDominant='" + largestOp + "', operatorDominantText='" + largestOpText + "' WHERE id = '" + id + "';"
                allSqls.append(sql)


        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(row)


    write_objects_to_csv(allStoreFrontItems, "result-storefront-items.csv")
    write_objects_to_csv(outlsetScoreObjects, "result-storefront-outlet-scores.csv")
    write_file(allSqls, "result-storefront-sql.sql")

def operator2text(operator):
    switch_dict = {
    
        "telkomsel": "Telkomsel",
        "indosat":"Indosat",
        "tri":"Tri",
        "axis":"Axis",
        "xl":"XL",
        "smartfren":"Smartfren",
        "byu": "By.U"
    }

    return switch_dict.get(operator)

    

def getStoreFrontItems(id, operators, allStoreFrontItems):
    for operator in operators:
        if(operator.percentage > 0):
        
            operatorText = operator2text(operator.operator.lower())
            item = { "operator": operator.operator.lower(), "operatorText": operatorText , "percentage": operator.percentage }
            item["upload_file_id"] = id
            item["visibility_percentage"] = operator.percentage
            item["visibility_score"] = operator.score
            item["tag"] = "recalculate"
            allStoreFrontItems.append(item)
    
    return allStoreFrontItems
    

def getTheLargestCoverageOperator( operators):    
    selOp = operators[0]
    for item in operators:
        if item.percentage > selOp.percentage:
            selOp = item
    return selOp
    
def write_file(texts, filepath):
    with open(filepath, 'w') as file:
        for line in texts:
            file.write(line + '\n')

def write_objects_to_csv(objects, filepath):

    item = objects[0]
    print("=========")
    try:
        item = vars(item)
    except:
        print("Not object. Skipping...")

    keys = list(item.keys())

    data = []
    for o in objects:
        if type(o) is dict:
            data.append(o)
        else:
            data.append(vars(o))

    with open(filepath, 'w') as csvfile: 
        writer = csv.DictWriter(csvfile, fieldnames = keys ) 
        writer.writeheader() 
        writer.writerows(data) 

if __name__ == "__main__":
    main()