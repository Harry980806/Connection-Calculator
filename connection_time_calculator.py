import pandas as pd
import numpy as np
import pytz
from pytz import timezone
from datetime import datetime,timedelta
import streamlit as st


@st.cache_data 
def load_data_excel(filename,sn):
    df = pd.read_excel(filename,sheet_name = sn)
    # time.sleep(20)
    return df


@st.cache_data 
def load_data_csv(filename):
    df = pd.read_csv(filename)
    # time.sleep(20)
    return df


def calculate_arrival_time (row):
    cur_blk_time = row['Total Blk time'].hour + row['Total Blk time'].minute/60
    return row['Dept Time'] + pd.DateOffset(hours=cur_blk_time)


# need to get data cleaning to be cached. 


@st.cache_data
def data_cleaning(df1,df2,df3):
    df = pd.concat([df1,df2])

    df['Day'] = df['Day'].astype(str)
    df['Dept Time'] = df['Dept Time'].astype(str)
    df['Dept Time'] = pd.to_datetime(df['Day'] + ' ' + df['Dept Time'])
    df['Dept Time'] = pd.to_datetime(df['Dept Time'])

    df3['airport'] = df3['airport-timezone'].str.split('     ').str[0]
    df3['timezone'] = df3['airport-timezone'].str.split('     ').str[1]


    t1 = pd.merge(df,df3, how = 'left',left_on = 'Dept Sta',right_on = 'airport')
    t1 = t1.drop(columns = ['airport-timezone','airport'])
    t = pd.merge(t1,df3, how = 'left',left_on = 'Arvl Sta',right_on = 'airport')
    t = t.drop(columns = ['airport-timezone','airport'])


    t['arrival_time_dept_tz'] = [None] * len(t)



    t['arrival_time_dept_tz'] = t.apply(calculate_arrival_time,axis = 1)

    t['arrival_time_local_tz'] = [None] * len(t)
    for i in range(0,len(t)):
        old_timezone = pytz.timezone(t['timezone_x'][i])
        new_timezone = pytz.timezone(t['timezone_y'][i])

        # two-step process
        localized_timestamp = old_timezone.localize(t['arrival_time_dept_tz'][i])
        new_timezone_timestamp = localized_timestamp.astimezone(new_timezone)
        t.iloc[i,-1] = new_timezone_timestamp
        
    t['arrival_time_local_tz'] = t['arrival_time_local_tz'].apply(lambda t: t.replace(tzinfo=None))

    return t



def main():


    pax= load_data_excel('S23_WB_NB_DH4_08Mar-28Oct.xlsx','S23 Pax Leg Sked')

    freighter = load_data_excel('W22_S23_Cargo Freight Sked_26Mar-28Oct.xlsx','Daily Leg Schedule')
    
    airport_timezone = load_data_csv('Airport timezone.csv')

    freighter = freighter[freighter['Day'].notnull()]
    freighter['Flt Num'] = freighter['Flt Num'].astype(int).astype(str)

    pax = pax[pax['Day'].notnull()]
    pax['Flt Num'] = pax['Flt Num'].astype(int).astype(str)

    t= data_cleaning(pax,freighter,airport_timezone)

    AWB_origin = st.selectbox(
    'Select AWB origin',
    t['Dept Sta'].unique().tolist())


    AWB_destination = st.selectbox(
    'Select AWB destination',
    t['Arvl Sta'].unique().tolist())

    AWB_date = st.date_input(
     "Select First Flight Date")
    AWB_date = str(AWB_date)

    AWB_date_new = datetime.strptime(AWB_date, "%Y-%m-%d")+ timedelta(days=7)


    if st.button('Show total travel time'):
        st.write('Calculating...')


        required_final_flights = t[(t['Arvl Sta'] == AWB_destination)&
                                            (t['Day'] >= AWB_date)&
                                            (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)

        # look if there are direct flights
        direct_flights = t[(t['Dept Sta'] == AWB_origin)&
                        (t['Arvl Sta'] == AWB_destination)&
                        (t['Day'] >= AWB_date)&
                          (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)

        # if yes, calculate direct flight time
        
        
        
        if len(direct_flights) != 0:
            st.markdown('There are direct flights')
            st.markdown('Flight time is ' + str(direct_flights['Total Blk time'][0]))
            st.markdown('Connection time is 0')
            st.markdown('Total travel time is ' + str(direct_flights['Total Blk time'][0]))
            st.markdown('These are direct flights for the next 7 days including the input flight date')
            st.table(direct_flights)

            
        else: # if there are no direct flights, and assume only 1 stop
            
            st.markdown('Direct flights not found')
            
            # get all flights scheduled to departure from AWB origin on the selected flight date
            
            
            # some logic change to be done here. (maybe show the next 7 days)
            first_flights_departed= t[(t['Dept Sta'] == AWB_origin)&
                                      (t['Day'] == AWB_date)].reset_index(drop = True)
            
            if len(first_flights_departed)== 0: # if there are no departing flights
                st.markdown('There are no flights departed from {}'.format(AWB_origin))
                
            else:
    
                # get all flights scheduled to arrive the AWB destinatiion
                required_second_flights = t[(t['Arvl Sta'] == AWB_destination)&
                                            (t['Day'] >= AWB_date)&
                                            (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)
                
                # find transit airport
                joint = pd.merge(
                    first_flights_departed,required_second_flights,how = 'inner',
                    left_on = 'Arvl Sta',right_on = 'Dept Sta',
                    suffixes = ['_f1','_f2'])
                
                if len(joint)!=0:
                    joint['connection time'] = [None] * len(joint)
                    for i in range(0,len(joint)):
                        f1_arrive = joint['arrival_time_local_tz_f1'][i]
                        f2_dept = joint['Dept Time_f2'][i]
                        
                    # calculate time between flight1 arrives and flight2 departures
                        joint.iloc[i,-1] = pd.Timedelta(f2_dept - f1_arrive)

                    joint = joint[joint['connection time'] > timedelta(minutes=120)].reset_index(drop = True)
                    
                    
                    # converting the timedelta column to int
                    
                    joint['connection time'] = joint['connection time'] / pd.Timedelta(hours=1)
            
                    # get minimum connection time.
                    final = joint[joint['connection time'] == joint['connection time'].min()].reset_index(drop = True)
            
                    # print the result
                    st.markdown('The Flight time for first flight is ' + str(final['Total Blk time_f1'][0].hour))
                    st.markdown(str(final['connection time'][0].days * 24 + final['connection time'][0].seconds/3600))
                    st.markdown(str(final['Total Blk time_f1'][0].hour+ 
                    final['connection time'][0].days * 24 + final['connection time'][0].seconds/3600 + 
                    final['Total Blk time_f2'][0].hour))
                    
                    st.markdown('Found flight route with 1 stop')
                    
                    st.code(final)
                    
                    for c in final.columns:
                        st.markdown(c)
                        st.markdown(type(final[c][0]))
                    
                    
                   
                    
                
                # there are no transit airport found
                else:
                    
                    st.markdown('No 1 stop flight schedule found')
                    
                    required_final_flights = t[(t['Arvl Sta'] == AWB_destination)&
                                            (t['Day'] >= AWB_date)&
                                            (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)
                    
                    # get the next possible destinations.
                    
                    required_next_flights = t[(t['Dept Sta'].isin(first_flights_departed['Arvl Sta'].tolist()))&
                                            (t['Arvl Sta'].isin(required_final_flights['Dept Sta'].tolist()))&
                                            (t['Day']>= AWB_date)&
                                            (t['Day']<= str(AWB_date_new)[:10])
                                            ].reset_index(drop = True)
                    
                    f1_f2_joint = pd.merge(
                    first_flights_departed,required_next_flights,how = 'left',
                    left_on = 'Arvl Sta',right_on = 'Dept Sta',
                    suffixes = ['_f1','_f2'])
                    
                    f2_f3_joint = pd.merge(
                    
                    f1_f2_joint,required_final_flights, how = 'left',
                    left_on = 'Arvl Sta_f2', right_on = 'Dept Sta'
                    )
                    
                    f2_f3_joint['connection_time_f1'] = [None] * len(f2_f3_joint)
                    for i in range(0,len(f2_f3_joint)):
                        f1_arrive = f2_f3_joint['arrival_time_local_tz_f1'][i]
                        f2_dept = f2_f3_joint['Dept Time_f2'][i]
                        
                    # calculate time between flight1 arrives and flight2 departures
                        f2_f3_joint.iloc[i,-1] = pd.Timedelta(f2_dept - f1_arrive)
                        
                        
                    
                    # require first connection time >= 2hrs
                    f2_f3_joint = f2_f3_joint[f2_f3_joint['connection_time_f1'] > 
                                            timedelta(minutes=120)].reset_index(drop = True)
                    
                    
                    f2_f3_joint['connection_time_f2'] = [None] * len(f2_f3_joint)
                    for i in range(0,len(f2_f3_joint)):
                        f2_arrive = f2_f3_joint['arrival_time_local_tz_f2'][i]
                        f3_dept = f2_f3_joint['Dept Time'][i]
                        
                    # calculate time between flight1 arrives and flight2 departures
                        f2_f3_joint.iloc[i,-1] = pd.Timedelta(f3_dept - f2_arrive)

                        
                    # require first connection time >= 2hrs
                    f2_f3_joint = f2_f3_joint[f2_f3_joint['connection_time_f2'] > 
                                            timedelta(minutes=120)].reset_index(drop = True)
                    
                    
                    f2_f3_joint['total_travel_time'] = [None] * len(f2_f3_joint)
                    for i in range(0,len(f2_f3_joint)):
                        f2_f3_joint.iloc[i,-1] = f2_f3_joint['Total Blk time_f1'][i].hour+\
                        f2_f3_joint['Total Blk time_f2'][i].hour+f2_f3_joint['Total Blk time'][i].hour+\
                        f2_f3_joint['connection_time_f1'][i].days * 24 + f2_f3_joint['connection_time_f1'][i].seconds/3600+\
                        f2_f3_joint['connection_time_f2'][i].days * 24 + f2_f3_joint['connection_time_f2'][i].seconds/3600    
                        
                    final =  f2_f3_joint[f2_f3_joint['total_travel_time'] == f2_f3_joint['total_travel_time'].min()].reset_index()

    st.markdown('Calculation Done')
                    
        
     

if __name__ == '__main__':
    main()
