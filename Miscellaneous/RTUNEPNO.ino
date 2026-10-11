//Relay shield for testing CLP-650 keyboard matrix
//To tune piano to A=432Hz
//Press A-1 and A#-1 simultaneously and hold them down
//Press A3 down and up 11 times (use tuner to verify pitch is changing)
//Release A-1 and A#-1

const int HOLD_TIME_MS = 200; //how long relay stays closed - tune this
const int GAP_USEC = 5000; // microsec between relay triggers
const int DLY_TIME = 1000; // delay between keypresses

//Piano key scanner requires 2 switches activated quickly for each key in order to detect velocity

const int BUTTON_PIN = 2;
const int TUNE_UP_PIN = 3;

const int LED_PIN = 13;

const int RELAY1_PIN = 22; // B 
const int RELAY2_PIN = 24; // B
const int RELAY3_PIN = 26; // A-1 first switch
const int RELAY4_PIN = 28; // A-1 second switch
const int RELAY5_PIN = 30; // A#-1 first switch
const int RELAY6_PIN = 32; // A#-1 second switch
const int RELAY7_PIN = 34; // A3 first switch
const int RELAY8_PIN = 36; // A3 second switch

const int RELAY_ON = HIGH;
const int RELAY_OFF = LOW;

void setup() {
  // put your setup code here, to run once:
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(TUNE_UP_PIN, INPUT_PULLUP);
  
  pinMode(LED_PIN, OUTPUT);
  digitalWrite (LED_PIN, HIGH);

  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);
  pinMode(RELAY3_PIN, OUTPUT);
  pinMode(RELAY4_PIN, OUTPUT);
  pinMode(RELAY5_PIN, OUTPUT);
  pinMode(RELAY6_PIN, OUTPUT);
  pinMode(RELAY7_PIN, OUTPUT);
  pinMode(RELAY8_PIN, OUTPUT);

  digitalWrite (RELAY1_PIN, RELAY_OFF);  
  digitalWrite (RELAY2_PIN, RELAY_OFF);
  digitalWrite (RELAY3_PIN, RELAY_OFF);  
  digitalWrite (RELAY4_PIN, RELAY_OFF);
  digitalWrite (RELAY5_PIN, RELAY_OFF);  
  digitalWrite (RELAY6_PIN, RELAY_OFF);
  digitalWrite (RELAY7_PIN, RELAY_OFF);  
  digitalWrite (RELAY8_PIN, RELAY_OFF);

  Serial.begin(9600);
  Serial1.begin(31250);
  Serial.println("Tuning piano to A432");

  delay(DLY_TIME);
  
  digitalWrite (LED_PIN, LOW);

  int buttonState = digitalRead (BUTTON_PIN);
  if (buttonState == HIGH) // skip tuning if button is pressed
  {
    int tuneUpState = digitalRead(TUNE_UP_PIN);
    
    keyDown (RELAY3_PIN, RELAY4_PIN, GAP_USEC);
    delay(DLY_TIME);

    int presses = 11;
    if (tuneUpState == LOW)
    {
      keyDown (RELAY1_PIN, RELAY2_PIN, GAP_USEC);
      presses = 5;      
    }
    else
    {
      keyDown (RELAY5_PIN, RELAY6_PIN, GAP_USEC);
    }
    delay(DLY_TIME);

    for (int i=0; i<presses; i++)
    {
      keyDown (RELAY7_PIN, RELAY8_PIN, GAP_USEC);
      delay(DLY_TIME);
      keyUp (RELAY7_PIN, RELAY8_PIN, GAP_USEC);
      delay(DLY_TIME);
    }
  
    keyUp (RELAY3_PIN, RELAY4_PIN, GAP_USEC);
    delay(DLY_TIME);
    if (tuneUpState == LOW)
    {
      keyUp (RELAY1_PIN, RELAY2_PIN, GAP_USEC);
    }
    else
    {
      keyUp (RELAY5_PIN, RELAY6_PIN, GAP_USEC);
    }
    delay(DLY_TIME);
  }
  else
  {
    while (buttonState == LOW) // wait for button release before entering loop
    {
      buttonState = digitalRead (BUTTON_PIN);
    }
    delay(100); // debounce
  }
  digitalWrite (LED_PIN, HIGH);
  delay(1000);
  digitalWrite (LED_PIN, LOW);
}

void keyDown (int pinA, int pinB, unsigned long gapMicros)
{
  unsigned long t0 = micros();
  digitalWrite (pinA, RELAY_ON);
  
  while ( micros() - t0 < gapMicros ) {
    // wait short interval
  }
  digitalWrite (pinB, RELAY_ON); 
  
  delay(HOLD_TIME_MS);
}

void keyUp (int pinA, int pinB, unsigned long gapMicros)
{
  unsigned long  t0 = micros();
  digitalWrite (pinB, RELAY_OFF);
  while ( micros() - t0 < gapMicros ) {
    // wait short interval
  }
  digitalWrite (pinA, RELAY_OFF);
  delay(HOLD_TIME_MS);  
}

void midiout(int cmd, int pitch, int velocity) {
  Serial1.write(cmd);
  Serial1.write(pitch);
  Serial1.write(velocity);
}

void loop() {
  // put your main code here, to run repeatedly:

  int buttonState = digitalRead (BUTTON_PIN);
  while (buttonState == HIGH)
  {
    buttonState = digitalRead (BUTTON_PIN);
  }
  digitalWrite (LED_PIN, HIGH);
  midiout(0xB0, 0x43, 0x7f);  // soft pedal
  while (buttonState == LOW)
  {
    buttonState = digitalRead (BUTTON_PIN);
  }
  digitalWrite (LED_PIN, LOW);
  midiout(0xB0, 0x43, 0x00);
  delay(100); // debounce
}


