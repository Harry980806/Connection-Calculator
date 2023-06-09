import pandas as pd
import numpy as np
import pytz
from pytz import timezone
from datetime import datetime,timedelta
import streamlit as st
from PIL import Image


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
    df['Equip'] = df['Equip'].astype(str)
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
    col1, col2 = st.columns(2)
    image1 = Image.open('WestJet_Leaf_Cargo_Hor_RGB (002).jpg')
    image2 = Image.open('WestJet_GTA_EN_TogetherWith (2997889_2323389).jpg')
    
    with col1:
     st.image(image1, width=400)

    with col2:
     st.image(image2, width=400)
    
    
    st.title('WestJet Cargo Flight Scanner')
    

    st.write('<p style="font-size:16px; color:Black;">This app would scan shipment end to end travel time (flight time + connection time) based on published flight schedule.</p>',
                 unsafe_allow_html=True)
    
     # disclaimer:
    st.write('<p style="font-size:14px; color:Black;">Designed by WestJet Cargo Analytics Team ©, CargoRM&Analytics@westjet.com</p>',
                 unsafe_allow_html=True)


    pax_and_freighter = load_data_excel('Combined Freighter_Pax _S23 skd_07Jul.xlsx','S23 Jul_Oct')

    pax= pax_and_freighter[pax_and_freighter['Equip']!= '7F8']
    
    freighter = pax_and_freighter[pax_and_freighter['Equip'] == '7F8']
    
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
    
    AircraftTypes = st.multiselect(
    'Select Aircraft Type',
    ['789','73H','73W','7F8','7M8','DH4','ALL'],
    ['789', '7F8'])
    

    AWB_date = st.date_input(
     "Select First Flight Date")
    AWB_date = str(AWB_date)
    
    

    AWB_date_new = datetime.strptime(AWB_date, "%Y-%m-%d")+ timedelta(days=7)


    if st.button('Show total travel time'):
        
        st.write('Calculating...')
        
        
        # Filter the Dataset to contain only the specified AircraftType
        if 'ALL' not in AircraftTypes:
            t = t[t['Equip'].isin(AircraftTypes)]
            
  
        required_final_flights = t[(t['Arvl Sta'] == AWB_destination)&
                                            (t['Day'] >= AWB_date)&
                                            (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)

        # look if there are direct flights in the next 7 days
        direct_flights = t[(t['Dept Sta'] == AWB_origin)&
                        (t['Arvl Sta'] == AWB_destination)&
                        (t['Day'] >= AWB_date)&
                          (t['Day']<= str(AWB_date_new)[:10])].reset_index(drop = True)

        # if yes, calculate direct flight time

        # look at if there are direct flights in the future:

        future_direct_flights= t[(t['Dept Sta'] == AWB_origin)&
                                (t['Arvl Sta'] == AWB_destination)&
                                (t['Day']>= str(AWB_date_new)[:10])].reset_index(drop = True)
        
        
        
        if len(direct_flights) != 0:
            st.markdown('✔️There are direct flights in the next 7 days')
            st.markdown('Flight time is ' + str(direct_flights['Total Blk time'][0]))
            st.markdown('Connection time is 0')
            st.markdown('Total travel time is ' + str(direct_flights['Total Blk time'][0]))
            st.markdown('These are direct flights for the next 7 days including the input flight date')
            st.table(direct_flights)

        
        elif (len(direct_flights) == 0) and (len(future_direct_flights)!= 0):
            st.markdown('🕵️ There are direct flights in the future, but not in the next 7 days.')
            st.markdown('Please adjust your proposed flight date and try again.')

            
        else: # if there are no direct flights, and assume only 1 stop
            
            st.markdown('❌No direct flights were found.')
            
            # get all flights scheduled to departure from AWB origin on the selected flight date
            
            
            # some logic change to be done here. (maybe show the next 7 days)
            first_flights_departed= t[(t['Dept Sta'] == AWB_origin)&
                                      (t['Day'] == AWB_date)].reset_index(drop = True)
            

            # if there are no departing flights
            if len(first_flights_departed)== 0:
                st.markdown('❌There are no flights departed from {} on the selected flight date'.format(AWB_origin))
                st.markdown('Please change your flight Date and/or Aircraft Type and try again.')
                
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

                    joint = joint[joint['connection time'] >= timedelta(minutes=90)].reset_index(drop = True)
                    
                    #  find not the minimum connection time, but the shortest overall flight time
                    
                    joint['total_travel_time'] = [None] * len(joint)
                    for i in range(0,len(joint)):
                        joint.iloc[i,-1] = joint['Total Blk time_f1'][i].hour+ joint['Total Blk time_f1'][0].minute/60+\
                        joint['Total Blk time_f2'][i].hour+ joint['Total Blk time_f2'][0].minute/60+\
                        joint['connection time'][i].days * 24 + joint['connection time'][i].seconds/3600
                    
                    
                    
                    
            
                    # get minimum connection time.
                    final = joint[joint['total_travel_time'] == joint['total_travel_time'].min()].reset_index(drop = True)
                    
                    
            
                    # print the result
                
                    result_df = final.rename(columns ={'Day_f1': 'F1:Flight Date',
                                                      'Weekday_f1': 'F1:DOW',
                                                      'Flt Num_f1': 'F1:Flight Number',
                                                      'Dept Sta_f1':'F1:Departure Station',
                                                      'Arvl Sta_f1':'F1:Arrival Station',
                                                      'Dept Time_f1':'F1:STD',
                                                      'Total Blk time_f1':'F1:Flight Time',
                                                      'Equip_f1' : 'F1:A/C',
                                                      'arrival_time_local_tz_f1':'F1:STA',
                                                       
                                                      'Day_f2': 'F2:Flight Date',
                                                      'Weekday_f2': 'F2:DOW',
                                                      'Flt Num_f2': 'F2:Flight Number',
                                                      'Dept Sta_f2':'F2:Departure Station',
                                                      'Arvl Sta_f2':'F2:Arrival Station',
                                                      'Dept Time_f2':'F2:STD',
                                                      'Total Blk time_f2':'F2:Flight Time',
                                                      'Equip_f2' : 'F2:A/C',
                                                      'arrival_time_local_tz_f2':'F2:STA'})
                    
                    result_df1 = result_df[['F1:Flight Number','F1:A/C','F1:STD',
                                            'F1:DOW', 'F1:Departure Station',
                                           'F1:Arrival Station','F1:STA',
                                          'F1:Flight Time']]
                    
                    
                    result_df2 = result_df[['F2:Flight Number','F2:A/C','F2:STD',
                                            'F2:DOW', 'F2:Departure Station',
                                           'F2:Arrival Station','F2:STA',
                                          'F2:Flight Time']]
                    
                    # Time length dataframe
                    
                    time_summary_df = pd.DataFrame(
                      columns = ['Time'],
                    index=pd.Index(['E2E time', 'total connection','total flying time']))
                    
                    # E2E Time
                    
                    time_summary_df['Time'][0] = str(
                                       round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+\
                                       final['connection time'][0].days * 24 + \
                                       final['connection time'][0].seconds/3600 +\
                                       final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60,1)) + ' hours'
                   
                    
                    # total flight time
                    time_summary_df['Time'][2] = str(
                                       round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+\
                                       final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60,1)) + ' hours'
                    
                    st.markdown('✔️Found flight route with 1 stop, please see the tables below for details.')
                    

#                     st.markdown('The scheduled first flight is from '  + final['Dept Sta_f1'][0] + ' to ' + final['Arvl Sta_f1'][0] + 
#                                ' ,on flight WS{}'.format(final['Flt Num_f1'][0]))
#                     st.markdown('The flight time for first flight is ' + str(round(final['Total Blk time_f1'][0].hour + 
#                                                                                    final['Total Blk time_f1'][0].minute/60,1)) + ' hours')
#                     st.markdown('The connection time at {} is: '.format(final['Dept Sta_f2'][0])+
#                                 str(round(final['connection time'][0].days * 24 + final['connection time'][0].seconds/3600,1)) + ' hours')
                    
#                     st.markdown('The scheduled second flight is from '  + final['Dept Sta_f2'][0] + ' to ' + final['Arvl Sta_f2'][0] + 
#                                ' ,on flight WS{}'.format(final['Flt Num_f2'][0]))
                    
#                     st.markdown('The flight time for second flight is ' + str(round(final['Total Blk time_f2'][0].hour + 
#                                                                                     final['Total Blk time_f2'][0].minute/60,1)) + ' hours')

                    
                   
        
        
        
#                     st.markdown('The total travel time is ' + 
#                                 str(round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+
#                                       final['connection time'][0].days * 24 + 
#                                       final['connection time'][0].seconds/3600 +
#                                       final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60,1)) +' hours')
                    
                    # converting the timedelta column to int
                    
                    final['connection time'] = final['connection time'] / pd.Timedelta(hours=1)
                    
                    
                    # connection time
                    time_summary_df['Time'][1] = str(round(final['connection time'][0],1)) + ' hours'
                    
                    st.markdown('Time Summary')
                    #st.markdown(final['connection time'][0])
                    
#                     total_seconds = final['connection time'][0].total_seconds()
#                     total_hours = total_seconds // 3600
#                     timestamp = datetime.time(hour=int(total_hours), minute=int((total_seconds % 3600) // 60), second=int(total_seconds % 60))

#                     st.markdown(timestamp)
                    st.table(time_summary_df)
                    
                    st.markdown('Details -- Flight 1')
                    st.table(result_df1.T)
                    
                    st.markdown('The connection time at {} is: '.format(final['Dept Sta_f2'][0])+
                                 str(round(final['connection time'][0],1)) +' hours')
                        
#                     st.markdown('The connection time at {} is: '.format(final['Dept Sta_f2'][0])+
#                                 str(round(final['connection time'][0].days * 24 + final['connection time'][0].seconds/3600,1)) + ' hours')
                    
                    st.markdown('Details -- Flight 2')
                    st.table(result_df2.T)
                    
             
                    
          
                    
                
                # there are no transit airport found
                else:
                    
                    st.markdown('❌No 1 stop flight schedule found')
                    
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
                    f2_f3_joint = f2_f3_joint[f2_f3_joint['connection_time_f1'] >= 
                                            timedelta(minutes=90)].reset_index(drop = True)
                    
                    
                    f2_f3_joint['connection_time_f2'] = [None] * len(f2_f3_joint)
                    for i in range(0,len(f2_f3_joint)):
                        f2_arrive = f2_f3_joint['arrival_time_local_tz_f2'][i]
                        f3_dept = f2_f3_joint['Dept Time'][i]
                        
                    # calculate time between flight1 arrives and flight2 departures
                        f2_f3_joint.iloc[i,-1] = pd.Timedelta(f3_dept - f2_arrive)

                        
                    # require first connection time >= 1.5 hrs
                    f2_f3_joint = f2_f3_joint[f2_f3_joint['connection_time_f2'] >=
                                            timedelta(minutes=90)].reset_index(drop = True)
                    
                    
                    f2_f3_joint['total_travel_time'] = [None] * len(f2_f3_joint)
                    for i in range(0,len(f2_f3_joint)):
                        f2_f3_joint.iloc[i,-1] = f2_f3_joint['Total Blk time_f1'][i].hour+f2_f3_joint['Total Blk time_f1'][i].minute/60+\
                        f2_f3_joint['Total Blk time_f2'][i].hour+ f2_f3_joint['Total Blk time_f2'][i].minute/60+\
                        f2_f3_joint['Total Blk time'][i].hour+ f2_f3_joint['Total Blk time'][i].minute/60+\
                        f2_f3_joint['connection_time_f1'][i].days * 24 + f2_f3_joint['connection_time_f1'][i].seconds/3600+\
                        f2_f3_joint['connection_time_f2'][i].days * 24 + f2_f3_joint['connection_time_f2'][i].seconds/3600    
                    
                    
                    
                    
           
                    
                    if len(f2_f3_joint)!=0:    
                        
                        st.markdown('✔️Found schedule with 2 stops')
                        
                        final =  f2_f3_joint[f2_f3_joint['total_travel_time'] == f2_f3_joint['total_travel_time'].min()].reset_index()



                        # if there are multiple flight schedule found, just pick the first one.

                        final = final.head(1)
                        
                        
                        # rename the dataframe for display:
                        
                        
                        result_df = final.rename(columns ={'Day_f1': 'F1:Flight Date',
                                                      'Weekday_f1': 'F1:DOW',
                                                      'Flt Num_f1': 'F1:Flight Number',
                                                      'Dept Sta_f1':'F1:Departure Station',
                                                      'Arvl Sta_f1':'F1:Arrival Station',
                                                      'Dept Time_f1':'F1:STD',
                                                      'Total Blk time_f1':'F1:Flight Time',
                                                      'Equip_f1' : 'F1:A/C',
                                                      'arrival_time_local_tz_f1':'F1:STA',
                                                       
                                                      'Day_f2': 'F2:Flight Date',
                                                      'Weekday_f2': 'F2:DOW',
                                                      'Flt Num_f2': 'F2:Flight Number',
                                                      'Dept Sta_f2':'F2:Departure Station',
                                                      'Arvl Sta_f2':'F2:Arrival Station',
                                                      'Dept Time_f2':'F2:STD',
                                                      'Total Blk time_f2':'F2:Flight Time',
                                                      'Equip_f2' : 'F2:A/C',
                                                      'arrival_time_local_tz_f2':'F2:STA',
                                                         
                                                      'Day': 'F3:Flight Date',
                                                      'Weekday': 'F3:DOW',
                                                      'Flt Num': 'F3:Flight Number',
                                                      'Dept Sta':'F3:Departure Station',
                                                      'Arvl Sta':'F3:Arrival Station',
                                                      'Dept Time':'F3:STD',
                                                      'Total Blk time':'F3:Flight Time',
                                                      'Equip' : 'F3:A/C',
                                                      'arrival_time_local_tz':'F3:STA'   
                                                         
                                                         })
                   
                    
                        result_df1 = result_df[['F1:Flight Number','F1:A/C','F1:STD',
                                            'F1:DOW', 'F1:Departure Station',
                                           'F1:Arrival Station','F1:STA',
                                          'F1:Flight Time']]
                    
                    
                        result_df2 = result_df[['F2:Flight Number','F2:A/C','F2:STD',
                                            'F2:DOW', 'F2:Departure Station',
                                           'F2:Arrival Station','F2:STA',
                                          'F2:Flight Time']]
                                                
                        result_df3 = result_df[['F3:Flight Number','F3:A/C','F3:STD',
                                            'F3:DOW', 'F3:Departure Station',
                                           'F3:Arrival Station','F3:STA',
                                          'F3:Flight Time']]                            
                    
                    # Time length dataframe
                    
                       





#                         st.markdown('The scheduled first flight is from '  + final['Dept Sta_f1'][0] + ' to ' + final['Arvl Sta_f1'][0] + 
#                                    ' ,on flight WS{}'.format(final['Flt Num_f1'][0]))

#                         st.markdown('The flight time for first flight is ' + str(round(final['Total Blk time_f1'][0].hour + 
#                                                                                        final['Total Blk time_f1'][0].minute/60,1)) + ' hours')

#                         st.markdown('The connection time at {} is: '.format(final['Dept Sta_f2'][0])+
#                                     str(round(final['connection_time_f1'][0].days * 24 + final['connection_time_f1'][0].seconds/3600,1)) + ' hours')

#                         st.markdown('The scheduled second flight is from '  + final['Dept Sta_f2'][0] + ' to ' + final['Arvl Sta_f2'][0] + 
#                                    ' ,on flight WS{}'.format(final['Flt Num_f2'][0]))

#                         st.markdown('The flight time for second flight is ' + str(round(final['Total Blk time_f2'][0].hour + 
#                                                                                         final['Total Blk time_f2'][0].minute/60,1)) + ' hours')

#                         st.markdown('The connection time at {} is: '.format(final['Dept Sta'][0])+
#                                     str(round(final['connection_time_f2'][0].days * 24 + final['connection_time_f2'][0].seconds/3600,1)) + ' hours')


#                         st.markdown('The scheduled third flight is from '  + final['Dept Sta'][0] + ' to ' + final['Arvl Sta'][0] + 
#                                    ' ,on flight WS{}'.format(final['Flt Num'][0]))

#                         st.markdown('The flight time for third flight is ' + str(round(final['Total Blk time'][0].hour + 
#                                                                                         final['Total Blk time'][0].minute/60,1)) + ' hours')

#                         st.markdown('The total travel time is ' + 
#                                     str(round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+
#                                           final['connection_time_f1'][0].days * 24 + 
#                                           final['connection_time_f1'][0].seconds/3600 +
#                                           final['connection_time_f2'][0].days * 24 + 
#                                           final['connection_time_f2'][0].seconds/3600 +
#                                           final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60+
#                                           final['Total Blk time'][0].hour + final['Total Blk time'][0].minute/60,1)) +' hours')


                        time_summary_df = pd.DataFrame(
                            columns = ['Time'],
                        index=pd.Index(['E2E time', 'total connection','total flying time']))
    
                        # E2E Time
                        time_summary_df['Time'][0] = str(round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+\
                                                final['connection_time_f1'][0].days * 24 + \
                                                final['connection_time_f1'][0].seconds/3600 +\
                                                final['connection_time_f2'][0].days * 24 +\
                                                final['connection_time_f2'][0].seconds/3600 +\
                                                final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60+\
                                                final['Total Blk time'][0].hour + final['Total Blk time'][0].minute/60,1)) +' hours'


                          # converting the timedelta column to int
                        final['connection_time_f1'] = final['connection_time_f1'] / pd.Timedelta(hours=1)
                        final['connection_time_f2'] = final['connection_time_f2'] / pd.Timedelta(hours=1)
                        final['total_travel_time']= final['total_travel_time'].astype(float).round(1)
                
                
                     
                        
                        # connection time
                        
                        time_summary_df['Time'][1] = str(round(final['connection_time_f1'][0],1)+round(final['connection_time_f2'][0],1))+' hours'
                        
                        # total flight time
                        time_summary_df['Time'][2] = str(round(final['Total Blk time_f1'][0].hour+ final['Total Blk time_f1'][0].minute/60+
                                                final['Total Blk time_f2'][0].hour + final['Total Blk time_f2'][0].minute/60+
                                                final['Total Blk time'][0].hour + final['Total Blk time'][0].minute/60,1)) +' hours'
                
                
                        st.markdown('Time Summary')
                        st.table(time_summary_df)
                        
                        

                                                
                                                
                        st.markdown('Details -- Flight1')
                        st.dataframe(result_df1.T)
                        st.markdown('Connection time at {}: '.format(final['Dept Sta_f2'][0])+str(round(final['connection_time_f1'][0],1)) +' hours')
                                                                                 
                        st.markdown('Details -- Flight2')
                        st.dataframe(result_df2.T)
                        
                        st.markdown('Connection time at {}: '.format(final['Dept Sta'][0])+str(round(final['connection_time_f2'][0],1))+' hours')
                        st.markdown('Details -- Flight3')
                        st.dataframe(result_df3.T)
                    
                    else: st.markdown('❌Can not find flight routes within 2 stops, please adjust the flight date and airCraft type and try again')

        st.markdown('Calculation Done')
        
       
                    
        
     

if __name__ == '__main__':
    main()
