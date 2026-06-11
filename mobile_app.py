from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
import requests
import json

# Configure window size for mobile
Window.size = (360, 640)

# CHANGE THIS TO YOUR COMPUTER'S IP ADDRESS
API_URL = "http://192.168.1.100:5000"


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        # Title
        title = Label(text='[color=#667eea]LIPO[/color]', font_size=40, markup=True)
        layout.add_widget(title)
        
        subtitle = Label(text='Fault Tracking App', font_size=18, color=(0.5, 0.5, 0.5, 1))
        layout.add_widget(subtitle)
        
        # Username
        self.username_input = TextInput(hint_text='Username', size_hint_y=None, height=50, padding=[10, 10])
        layout.add_widget(self.username_input)
        
        # Password
        self.password_input = TextInput(hint_text='Password', password=True, size_hint_y=None, height=50, padding=[10, 10])
        layout.add_widget(self.password_input)
        
        # Login Button
        login_btn = Button(text='LOGIN', size_hint_y=None, height=50, background_color=(0.4, 0.49, 0.92, 1))
        login_btn.bind(on_press=self.login)
        layout.add_widget(login_btn)
        
        # Signup Link
        signup_btn = Button(text='Create Account', size_hint_y=None, height=40, background_color=(0.29, 0.75, 0.29, 1))
        signup_btn.bind(on_press=self.go_to_signup)
        layout.add_widget(signup_btn)
        
        self.error_label = Label(text='', color=(1, 0, 0, 1), font_size=14)
        layout.add_widget(self.error_label)
        
        self.add_widget(layout)
    
    def login(self, instance):
        username = self.username_input.text
        password = self.password_input.text
        
        if not username or not password:
            self.error_label.text = "Please enter username and password"
            return
        
        try:
            response = requests.post(
                f"{API_URL}/api/login",
                json={"username": username, "password": password},
                timeout=10
            )
            data = response.json()
            
            if data.get('success'):
                self.manager.current_user = data['user']
                self.manager.current_user['token'] = 'logged_in'
                self.error_label.text = ""
                
                if data['user']['role'] == 'admin':
                    self.manager.current = 'admin'
                else:
                    self.manager.current = 'worker'
            else:
                self.error_label.text = data.get('message', 'Login failed')
        except Exception as e:
            self.error_label.text = f"Connection error: {str(e)}"
    
    def go_to_signup(self, instance):
        self.manager.current = 'signup'


class SignupScreen(Screen):
    def __init__(self, **kwargs):
        super(SignupScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        title = Label(text='[color=#667eea]Sign Up[/color]', font_size=30, markup=True)
        layout.add_widget(title)
        
        self.username_input = TextInput(hint_text='Username', size_hint_y=None, height=50, padding=[10, 10])
        layout.add_widget(self.username_input)
        
        # Department Spinner
        self.department_spinner = Spinner(
            text='Select Department',
            values=('Production', 'Quality', 'Maintenance', 'Store', 'HR', 'IT', 'Finance'),
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.department_spinner)
        
        self.password_input = TextInput(hint_text='Password', password=True, size_hint_y=None, height=50, padding=[10, 10])
        layout.add_widget(self.password_input)
        
        self.confirm_password_input = TextInput(hint_text='Confirm Password', password=True, size_hint_y=None, height=50, padding=[10, 10])
        layout.add_widget(self.confirm_password_input)
        
        signup_btn = Button(text='SIGN UP', size_hint_y=None, height=50, background_color=(0.29, 0.75, 0.29, 1))
        signup_btn.bind(on_press=self.signup)
        layout.add_widget(signup_btn)
        
        back_btn = Button(text='Back to Login', size_hint_y=None, height=40)
        back_btn.bind(on_press=self.go_back)
        layout.add_widget(back_btn)
        
        self.error_label = Label(text='', color=(1, 0, 0, 1), font_size=14)
        layout.add_widget(self.error_label)
        
        self.add_widget(layout)
    
    def signup(self, instance):
        username = self.username_input.text
        password = self.password_input.text
        confirm_password = self.confirm_password_input.text
        department = self.department_spinner.text
        
        if not username or not password or department == 'Select Department':
            self.error_label.text = "Please fill all fields"
            return
        
        if password != confirm_password:
            self.error_label.text = "Passwords do not match"
            return
        
        try:
            response = requests.post(
                f"{API_URL}/api/signup",
                json={"username": username, "password": password, "department": department},
                timeout=10
            )
            data = response.json()
            
            if data.get('success'):
                self.error_label.text = ""
                self.manager.current = 'login'
            else:
                self.error_label.text = data.get('message', 'Signup failed')
        except Exception as e:
            self.error_label.text = f"Error: {str(e)}"
    
    def go_back(self, instance):
        self.manager.current = 'login'


class AdminScreen(Screen):
    def __init__(self, **kwargs):
        super(AdminScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Header
        header = BoxLayout(size_hint_y=None, height=60)
        title = Label(text='LIPO Admin', font_size=24, color=(0.4, 0.49, 0.92, 1))
        header.add_widget(title)
        logout_btn = Button(text='Logout', size_hint_x=None, width=100, background_color=(0.9, 0.3, 0.3, 1))
        logout_btn.bind(on_press=self.logout)
        header.add_widget(logout_btn)
        layout.add_widget(header)
        
        # Reports list
        self.reports_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.reports_layout.bind(minimum_height=self.reports_layout.setter('height'))
        
        scroll_view = ScrollView()
        scroll_view.add_widget(self.reports_layout)
        layout.add_widget(scroll_view)
        
        # Refresh button
        refresh_btn = Button(text='REFRESH', size_hint_y=None, height=50, background_color=(0.4, 0.49, 0.92, 1))
        refresh_btn.bind(on_press=self.load_reports)
        layout.add_widget(refresh_btn)
        
        self.add_widget(layout)
    
    def on_enter(self):
        self.load_reports(None)
    
    def load_reports(self, instance):
        try:
            # Get user from manager
            user = self.manager.current_user
            response = requests.get(
                f"{API_URL}/api/reports",
                headers={"Authorization": f"Bearer {user.get('token', 'logged_in')}"},
                timeout=10
            )
            data = response.json()
            
            self.reports_layout.clear_widgets()
            
            if data.get('success'):
                for report in data.get('reports', []):
                    card = BoxLayout(orientation='vertical', padding=10, size_hint_y=None, height=120)
                    card.add_widget(Label(text=f"ID: {report['id']} - {report['issue_description'][:30]}...", font_size=14))
                    card.add_widget(Label(text=f"Date: {report['created_at']}", font_size=12, color=(0.5, 0.5, 0.5, 1)))
                    self.reports_layout.add_widget(card)
        except Exception as e:
            print(f"Error loading reports: {e}")
    
    def logout(self, instance):
        self.manager.current = 'login'


class WorkerScreen(Screen):
    def __init__(self, **kwargs):
        super(WorkerScreen, self).__init__(**kwargs)
        
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Header
        header = BoxLayout(size_hint_y=None, height=60)
        title = Label(text='My Reports', font_size=24, color=(0.29, 0.75, 0.29, 1))
        header.add_widget(title)
        report_btn = Button(text='New', size_hint_x=None, width=80, background_color=(0.29, 0.75, 0.29, 1))
        report_btn.bind(on_press=self.new_report)
        header.add_widget(report_btn)
        logout_btn = Button(text='Logout', size_hint_x=None, width=80, background_color=(0.9, 0.3, 0.3, 1))
        logout_btn.bind(on_press=self.logout)
        header.add_widget(logout_btn)
        layout.add_widget(header)
        
        # Reports list
        self.reports_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.reports_layout.bind(minimum_height=self.reports_layout.setter('height'))
        
        scroll_view = ScrollView()
        scroll_view.add_widget(self.reports_layout)
        layout.add_widget(scroll_view)
        
        # Refresh button
        refresh_btn = Button(text='REFRESH', size_hint_y=None, height=50, background_color=(0.4, 0.49, 0.92, 1))
        refresh_btn.bind(on_press=self.load_reports)
        layout.add_widget(refresh_btn)
        
        self.add_widget(layout)
    
    def on_enter(self):
        self.load_reports(None)
    
    def load_reports(self, instance):
        try:
            user = self.manager.current_user
            response = requests.get(
                f"{API_URL}/api/reports",
                timeout=10
            )
            data = response.json()
            
            self.reports_layout.clear_widgets()
            
            if data.get('success'):
                for report in data.get('reports', []):
                    card = BoxLayout(orientation='vertical', padding=10, size_hint_y=None, height=100)
                    card.add_widget(Label(text=f"#{report['id']}: {report['issue_description'][:40]}...", font_size=14))
                    card.add_widget(Label(text=f"Date: {report['created_at']}", font_size=12, color=(0.5, 0.5, 0.5, 1)))
                    self.reports_layout.add_widget(card)
        except Exception as e:
            print(f"Error: {e}")
    
    def new_report(self, instance):
        self.manager.current = 'create_report'
    
    def logout(self, instance):
        self.manager.current = 'login'


class CreateReportScreen(Screen):
    def __init__(self, **kwargs):
        super(CreateReportScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        title = Label(text='Submit Report', font_size=24, color=(0.29, 0.75, 0.29, 1))
        layout.add_widget(title)
        
        self.description_input = TextInput(hint_text='Describe the issue...', multiline=True, size_hint_y=None, height=150, padding=[10, 10])
        layout.add_widget(self.description_input)
        
        # Submit Button
        submit_btn = Button(text='SUBMIT', size_hint_y=None, height=50, background_color=(0.29, 0.75, 0.29, 1))
        submit_btn.bind(on_press=self.submit_report)
        layout.add_widget(submit_btn)
        
        # Back Button
        back_btn = Button(text='BACK', size_hint_y=None, height=40)
        back_btn.bind(on_press=self.go_back)
        layout.add_widget(back_btn)
        
        self.error_label = Label(text='', color=(0, 1, 0, 1), font_size=14)
        layout.add_widget(self.error_label)
        
        self.add_widget(layout)
    
    def submit_report(self, instance):
        description = self.description_input.text
        
        if not description:
            self.error_label.text = "Please enter description"
            return
        
        try:
            response = requests.post(
                f"{API_URL}/api/create_report",
                json={"issue_description": description},
                timeout=10
            )
            data = response.json()
            
            if data.get('success'):
                self.error_label.text = "Report submitted!"
                self.description_input.text = ""
                self.manager.current = 'worker'
            else:
                self.error_label.text = data.get('message', 'Failed')
        except Exception as e:
            self.error_label.text = f"Error: {str(e)}"
    
    def go_back(self, instance):
        self.manager.current = 'worker'


class LEAPOApp(App):
    def build(self):
        # Create screen manager
        sm = ScreenManager()
        
        # Add screens
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(SignupScreen(name='signup'))
        sm.add_widget(AdminScreen(name='admin'))
        sm.add_widget(WorkerScreen(name='worker'))
        sm.add_widget(CreateReportScreen(name='create_report'))
        
        # Initialize current_user
        sm.current_user = {}
        
        return sm


if __name__ == '__main__':
    LIPOApp().run() 