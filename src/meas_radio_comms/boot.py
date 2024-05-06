import usb_cdc

# Enable console and data
usb_cdc.enable(console=True, data=True)
print("Enabled console and data ports.")