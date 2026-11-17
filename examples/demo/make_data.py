"""Writes the fictional demo data: 200 customers and 800 orders, seed 7.

Usage: python3 make_data.py sample-data
"""
import csv, random, sys, datetime
random.seed(7)
out=sys.argv[1]
first=["Alice","Bob","Carol","David","Erin","Frank","Grace","Henry","Ivy","Jack","Kara","Liam","Maya","Noah","Olivia","Paul"]
last=["Anderson","Brown","Carter","Diaz","Evans","Foster","Garcia","Hughes","Ito","Jones","Kim","Lopez","Miller","Nguyen","Owens","Patel"]
def luhn(d):
    s=0
    for i,c in enumerate(reversed(d)):
        n=int(c)
        if i%2==1: n*=2; n-= 9 if n>9 else 0
        s+=n
    return str((10-s%10)%10)
custs=[]
with open(f"{out}/customers.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["customer_id","first_name","last_name","email","ssn","card_number","dob","zip","country","notes"])
    for i in range(1,201):
        fn,ln=random.choice(first),random.choice(last)
        cid=f"C{i:05d}"; custs.append(cid)
        ssn=f"{random.randint(100,899)}-{random.randint(10,99)}-{random.randint(1000,9999)}"
        body="4"+"".join(str(random.randint(0,9)) for _ in range(14)); card=body+luhn(body+"0")
        dob=datetime.date(1950,1,1)+datetime.timedelta(days=random.randint(0,18000))
        email=f"{fn.lower()}.{ln.lower()}{i}@example.com"
        notes=random.choice([f"Called from 555-{random.randint(100,999)}-{random.randint(1000,9999)} about billing",
            f"Customer asked to update email to {email}",
            f"Verified identity with SSN {ssn}",
            "Prefers contact by mail"])
        w.writerow([cid,fn,ln,email,ssn,card,dob.isoformat(),f"{random.randint(10000,99999)}",random.choice(["US","US","US","DE"]),notes])
with open(f"{out}/orders.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["order_id","customer_id","order_date","amount","status"])
    for j in range(1,801):
        d=datetime.date(2025,1,1)+datetime.timedelta(days=random.randint(0,320))
        w.writerow([f"O{j:06d}",random.choice(custs),d.isoformat(),f"{random.uniform(5,500):.2f}",random.choice(["shipped","shipped","returned","pending"])])
